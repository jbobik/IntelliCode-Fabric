"""
Fine-tuning engine using LoRA/QLoRA
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global status tracker
_fine_tune_status = {
    "running": False,
    "progress": 0,
    "epoch": 0,
    "total_epochs": 0,
    "loss": 0,
    "message": "Idle",
}


class FineTuner:
    def __init__(self, config: dict):
        self.config = config
        self.ft_config = config.get("fine_tuning", {})
        self.models_dir = Path(__file__).parent.parent / "models"
        self.data_dir = Path(__file__).parent.parent / "data"

    @staticmethod
    def get_status() -> dict:
        return _fine_tune_status

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
                "loss": 0,
                "message": "Preparing data...",
            }

            # Step 1: Prepare training data
            dataset = await self._prepare_dataset(project_path)

            _fine_tune_status["message"] = "Loading base model..."
            _fine_tune_status["progress"] = 10

            # Step 2: Load base model
            model_info = None
            for m in self.config["models"]["available"]:
                if m["id"] == model_id:
                    model_info = m
                    break
            if not model_info:
                raise ValueError(f"Model {model_id} not found")

            # Step 3: Run fine-tuning in executor
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
            raise

    async def _prepare_dataset(self, project_path: str) -> list[dict]:
        """Prepare fine-tuning dataset from project codebase"""
        dataset = []
        project = Path(project_path)

        supported_ext = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}

        for ext in supported_ext:
            for f in project.rglob(f"*{ext}"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if len(content.strip()) < 50:
                        continue

                    rel_path = str(f.relative_to(project))

                    # Create training examples from docstrings/comments → code
                    examples = self._extract_examples(content, rel_path, ext)
                    dataset.extend(examples)

                    # Also add file-level completion examples
                    if len(content) > 100:
                        midpoint = len(content) // 2
                        # Find a good split point (end of line)
                        split_idx = content.rfind('\n', 0, midpoint)
                        if split_idx > 0:
                            dataset.append({
                                "prompt": f"# File: {rel_path}\n{content[:split_idx]}",
                                "completion": content[split_idx:split_idx + 500],
                            })

                except Exception as e:
                    logger.warning(f"Error processing {f}: {e}")

        logger.info(f"Prepared {len(dataset)} training examples")
        return dataset

    def _extract_examples(self, content: str, file_path: str, ext: str) -> list[dict]:
        """Extract prompt-completion pairs from code"""
        examples = []

        if ext == ".py":
            # Extract function docstring → implementation pairs
            pattern = r'(def\s+\w+.*?:\s*\n\s*""".*?""")\s*\n(.*?)(?=\ndef\s|\nclass\s|\Z)'
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                signature_and_doc = match.group(1).strip()
                implementation = match.group(2).strip()
                if len(implementation) > 20:
                    examples.append({
                        "prompt": f"# File: {file_path}\n{signature_and_doc}\n# Implementation:",
                        "completion": implementation[:800],
                    })

        elif ext in (".js", ".ts", ".tsx", ".jsx"):
            # JSDoc → function pairs
            pattern = r'(/\*\*.*?\*/)\s*\n\s*((?:export\s+)?(?:async\s+)?(?:function|const|class)\s+\w+.*?)(?=\n(?:export|function|class|const|/\*\*)|\Z)'
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                jsdoc = match.group(1).strip()
                impl = match.group(2).strip()
                if len(impl) > 20:
                    examples.append({
                        "prompt": f"// File: {file_path}\n{jsdoc}\n// Implementation:",
                        "completion": impl[:800],
                    })

        return examples

    def _fine_tune_sync(self, model_info: dict, dataset: list[dict], epochs: int) -> dict:
        """Synchronous fine-tuning with LoRA"""
        global _fine_tune_status

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer
        from datasets import Dataset

        repo = model_info["repo"]
        model_id = model_info["id"]
        output_dir = str(self.models_dir / f"{model_id}-finetuned")

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Quantized model for QLoRA
        device = "cuda" if torch.cuda.is_available() else "cpu"

        if device == "cuda":
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
        else:
            model = AutoModelForCausalLM.from_pretrained(
                repo,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )

        # LoRA config
        lora_config = LoraConfig(
            r=self.ft_config.get("lora_r", 16),
            lora_alpha=self.ft_config.get("lora_alpha", 32),
            lora_dropout=self.ft_config.get("lora_dropout", 0.05),
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )

        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

        _fine_tune_status["message"] = "Preparing training data..."
        _fine_tune_status["progress"] = 20

        # Format dataset
        formatted = []
        for item in dataset:
            text = f"{item['prompt']}\n{item['completion']}{tokenizer.eos_token}"
            formatted.append({"text": text})

        if len(formatted) < 5:
            raise ValueError(f"Not enough training examples ({len(formatted)}). Need at least 5.")

        hf_dataset = Dataset.from_list(formatted)

        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=self.ft_config.get("batch_size", 4),
            gradient_accumulation_steps=self.ft_config.get("gradient_accumulation_steps", 4),
            learning_rate=self.ft_config.get("learning_rate", 2e-4),
            warmup_ratio=self.ft_config.get("warmup_ratio", 0.03),
            logging_steps=10,
            save_strategy="epoch",
            fp16=device == "cuda",
            optim="adamw_torch",
            report_to="none",
            max_grad_norm=0.3,
            lr_scheduler_type="cosine",
        )

        _fine_tune_status["message"] = "Training..."
        _fine_tune_status["progress"] = 30

        # Custom callback for progress
        from transformers import TrainerCallback

        class ProgressCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if state.global_step > 0 and logs:
                    progress = min(90, 30 + int(60 * state.global_step / state.max_steps))
                    _fine_tune_status.update({
                        "progress": progress,
                        "epoch": int(state.epoch) if state.epoch else 0,
                        "loss": logs.get("loss", 0),
                        "message": f"Training... Step {state.global_step}/{state.max_steps}",
                    })

        # Train
        trainer = SFTTrainer(
            model=model,
            train_dataset=hf_dataset,
            args=training_args,
            tokenizer=tokenizer,
            dataset_text_field="text",
            max_seq_length=self.ft_config.get("max_seq_length", 1024),
            callbacks=[ProgressCallback()],
        )

        trainer.train()

        # Save
        _fine_tune_status["message"] = "Saving model..."
        _fine_tune_status["progress"] = 95

        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

        return {
            "status": "ok",
            "output_dir": output_dir,
            "num_examples": len(formatted),
            "epochs": epochs,
        }