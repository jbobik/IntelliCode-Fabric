"""
Fine-tuning engine using QLoRA (Quantized LoRA).

Как работает:
1. Сканирует проект и извлекает пары (prompt → completion)
   из docstrings, комментариев, сигнатур функций
2. Загружает базовую модель в 4-bit
3. Применяет LoRA адаптеры к attention-слоям
4. Обучает только LoRA веса (~0.1% параметров)
5. Сохраняет только адаптер (~50-100MB вместо гигабайтов)
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальный статус дообучения
_fine_tune_status = {
    "running": False,
    "progress": 0,
    "epoch": 0,
    "total_epochs": 0,
    "loss": 0.0,
    "message": "Idle",
    "examples_count": 0,
}


class FineTuner:
    def __init__(self, config: dict):
        self.config = config
        self.ft_config = config.get("fine_tuning", {})
        self.models_dir = Path(__file__).parent.parent / "models"
        self.data_dir = Path(__file__).parent.parent / "data"

    @staticmethod
    def get_status() -> dict:
        return _fine_tune_status.copy()

    async def fine_tune(self, project_path: str, model_id: str, epochs: int = 3) -> dict:
        global _fine_tune_status

        if _fine_tune_status["running"]:
            return {"status": "error", "message": "Fine-tuning already in progress"}

        try:
            _fine_tune_status = {
                "running": True,
                "progress": 0,
                "epoch": 0,
                "total_epochs": epochs,
                "loss": 0.0,
                "message": "Preparing training data...",
                "examples_count": 0,
            }

            # ── Шаг 1: Подготовка данных ──
            logger.info(f"Preparing fine-tuning data from {project_path}")
            dataset = await self._prepare_dataset(project_path)

            _fine_tune_status["examples_count"] = len(dataset)
            _fine_tune_status["message"] = f"Prepared {len(dataset)} training examples"
            _fine_tune_status["progress"] = 10
            logger.info(f"Prepared {len(dataset)} training examples")

            if len(dataset) < 5:
                _fine_tune_status.update({
                    "running": False,
                    "message": f"Not enough training data ({len(dataset)} examples). Need at least 5.",
                })
                return {
                    "status": "error",
                    "message": f"Not enough training examples ({len(dataset)}). Need at least 5.",
                }

            # ── Шаг 2: Находим модель ──
            model_info = None
            for m in self.config["models"]["available"]:
                if m["id"] == model_id:
                    model_info = m
                    break
            if not model_info:
                raise ValueError(f"Model {model_id} not found in config")

            _fine_tune_status["message"] = "Loading base model for fine-tuning..."
            _fine_tune_status["progress"] = 15

            # ── Шаг 3: Запускаем обучение ──
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._fine_tune_sync(model_info, dataset, epochs)
            )

            _fine_tune_status.update({
                "running": False,
                "progress": 100,
                "message": "Fine-tuning complete!",
            })

            return result

        except Exception as e:
            _fine_tune_status.update({
                "running": False,
                "message": f"Error: {str(e)}",
            })
            logger.error(f"Fine-tuning error: {e}")
            raise

    async def _prepare_dataset(self, project_path: str) -> list[dict]:
        """
        Извлекает обучающие примеры из кодовой базы проекта.

        Стратегии извлечения:
        1. docstring/JSDoc → реализация функции
        2. начало файла → продолжение файла (completion)
        3. комментарий → следующий блок кода
        """
        dataset = []
        project = Path(project_path)
        supported_ext = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}
        ignore_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}

        for f in project.rglob("*"):
            if f.suffix not in supported_ext:
                continue
            if any(ig in f.parts for ig in ignore_dirs):
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if len(content.strip()) < 50:
                    continue

                rel_path = str(f.relative_to(project))

                # ── Стратегия 1: docstring → implementation ──
                examples = self._extract_docstring_examples(content, rel_path, f.suffix)
                dataset.extend(examples)

                # ── Стратегия 2: file completion ──
                if len(content) > 100:
                    lines = content.split('\n')
                    if len(lines) > 10:
                        mid = len(lines) // 2
                        dataset.append({
                            "text": f"# File: {rel_path}\n{content[:1500]}"
                        })

                # ── Стратегия 3: comment → code ──
                comment_examples = self._extract_comment_examples(content, rel_path, f.suffix)
                dataset.extend(comment_examples)

            except Exception as e:
                logger.warning(f"Error processing {f}: {e}")

        logger.info(f"Extracted {len(dataset)} training examples")
        return dataset

    def _extract_docstring_examples(self, content: str, file_path: str, ext: str) -> list[dict]:
        """Извлекает пары docstring → implementation"""
        examples = []

        if ext == ".py":
            pattern = r'(def\s+\w+[^:]*:\s*\n\s*"""[^"]*""")\s*\n(.*?)(?=\ndef\s|\nclass\s|\Z)'
            for match in re.finditer(pattern, content, re.DOTALL):
                sig = match.group(1).strip()
                impl = match.group(2).strip()
                if len(impl) > 20:
                    examples.append({
                        "text": f"# File: {file_path}\n{sig}\n{impl[:800]}"
                    })

        elif ext in (".js", ".ts", ".tsx", ".jsx"):
            pattern = r'(/\*\*[^*]*\*/)\s*\n\s*((?:export\s+)?(?:async\s+)?(?:function|const|class)\s+\w+[^{]*\{.*?)(?=\n(?:export|function|class|const|/\*\*)|\Z)'
            for match in re.finditer(pattern, content, re.DOTALL):
                jsdoc = match.group(1).strip()
                impl = match.group(2).strip()
                if len(impl) > 20:
                    examples.append({
                        "text": f"// File: {file_path}\n{jsdoc}\n{impl[:800]}"
                    })

        return examples

    def _extract_comment_examples(self, content: str, file_path: str, ext: str) -> list[dict]:
        """Извлекает пары comment → code block"""
        examples = []
        lines = content.split('\n')

        comment_prefixes = {'#'} if ext == '.py' else {'//'}

        i = 0
        while i < len(lines) - 1:
            line = lines[i].strip()
            is_comment = any(line.startswith(p) for p in comment_prefixes)

            if is_comment and len(line) > 10:
                # Собираем блок кода после комментария
                code_lines = []
                j = i + 1
                while j < len(lines) and j < i + 20:
                    next_line = lines[j].strip()
                    if not next_line:
                        j += 1
                        continue
                    if any(next_line.startswith(p) for p in comment_prefixes):
                        break
                    code_lines.append(lines[j])
                    j += 1

                if len(code_lines) >= 2:
                    code_block = '\n'.join(code_lines)
                    if len(code_block) > 30:
                        examples.append({
                            "text": f"# File: {file_path}\n{line}\n{code_block[:500]}"
                        })
                i = j
            else:
                i += 1

        return examples

    def _fine_tune_sync(self, model_info: dict, dataset: list[dict], epochs: int) -> dict:
        """Синхронное дообучение с QLoRA"""
        global _fine_tune_status

        import torch

        # Проверяем доступность необходимых библиотек
        try:
            from transformers import (
                AutoModelForCausalLM, AutoTokenizer,
                TrainingArguments, TrainerCallback,
            )
            from peft import LoraConfig, get_peft_model
            from trl import SFTTrainer
            from datasets import Dataset
        except ImportError as e:
            raise RuntimeError(
                f"Fine-tuning requires additional packages. Install them:\n"
                f"pip install peft trl datasets\n"
                f"Missing: {e}"
            )

        repo = model_info["repo"]
        model_id = model_info["id"]
        output_dir = str(self.models_dir / f"{model_id}-finetuned")

        _fine_tune_status["message"] = "Loading tokenizer..."
        _fine_tune_status["progress"] = 20

        # ── Tokenizer ──
        tokenizer = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        _fine_tune_status["message"] = "Loading base model..."
        _fine_tune_status["progress"] = 25

        # ── Base model ──
        device = "cuda" if torch.cuda.is_available() else "cpu"

        if device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                from peft import prepare_model_for_kbit_training

                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                model = AutoModelForCausalLM.from_pretrained(
                    repo,
                    quantization_config=quant_config,
                    device_map="auto",
                    trust_remote_code=True,
                )
                model = prepare_model_for_kbit_training(model)
                logger.info("Base model loaded in 4-bit for QLoRA")
            except ImportError:
                logger.warning("bitsandbytes not available, loading in full precision")
                model = AutoModelForCausalLM.from_pretrained(
                    repo, trust_remote_code=True, torch_dtype=torch.float16,
                )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                repo, trust_remote_code=True, torch_dtype=torch.float32,
            )

        _fine_tune_status["message"] = "Applying LoRA adapters..."
        _fine_tune_status["progress"] = 30

        # ── LoRA config ──
        lora_config = LoraConfig(
            r=self.ft_config.get("lora_r", 16),
            lora_alpha=self.ft_config.get("lora_alpha", 32),
            lora_dropout=self.ft_config.get("lora_dropout", 0.05),
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        model = get_peft_model(model, lora_config)

        trainable, total = 0, 0
        for p in model.parameters():
            total += p.numel()
            if p.requires_grad:
                trainable += p.numel()
        logger.info(f"LoRA: trainable={trainable:,} / total={total:,} ({100*trainable/total:.2f}%)")

        _fine_tune_status["message"] = "Preparing dataset..."
        _fine_tune_status["progress"] = 35

        # ── Dataset ──
        # Добавляем EOS токен к каждому примеру
        formatted = []
        for item in dataset:
            text = item["text"]
            if not text.endswith(tokenizer.eos_token):
                text += tokenizer.eos_token
            formatted.append({"text": text})

        hf_dataset = Dataset.from_list(formatted)

        # ── Training args ──
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=self.ft_config.get("batch_size", 2),
            gradient_accumulation_steps=self.ft_config.get("gradient_accumulation_steps", 4),
            learning_rate=self.ft_config.get("learning_rate", 2e-4),
            warmup_ratio=self.ft_config.get("warmup_ratio", 0.03),
            logging_steps=5,
            save_strategy="epoch",
            fp16=(device == "cuda"),
            optim="adamw_torch",
            report_to="none",
            max_grad_norm=0.3,
            lr_scheduler_type="cosine",
            remove_unused_columns=False,
        )

        _fine_tune_status["message"] = "Training started..."
        _fine_tune_status["progress"] = 40

        # ── Progress callback ──
        class ProgressCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if state.global_step > 0 and logs:
                    progress = min(95, 40 + int(55 * state.global_step / max(state.max_steps, 1)))
                    _fine_tune_status.update({
                        "progress": progress,
                        "epoch": int(state.epoch) if state.epoch else 0,
                        "loss": round(logs.get("loss", 0), 4),
                        "message": f"Training... Step {state.global_step}/{state.max_steps}, Loss: {logs.get('loss', 0):.4f}",
                    })

        # ── Train! ──
        trainer = SFTTrainer(
            model=model,
            train_dataset=hf_dataset,
            args=training_args,
            tokenizer=tokenizer,
            dataset_text_field="text",
            max_seq_length=self.ft_config.get("max_seq_length", 1024),
            callbacks=[ProgressCallback()],
        )

        logger.info("Starting training...")
        trainer.train()

        # ── Save ──
        _fine_tune_status["message"] = "Saving fine-tuned model..."
        _fine_tune_status["progress"] = 97

        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

        logger.info(f"Fine-tuned model saved to {output_dir}")

        return {
            "status": "ok",
            "output_dir": output_dir,
            "num_examples": len(formatted),
            "epochs": epochs,
            "trainable_params": trainable,
            "total_params": total,
        }