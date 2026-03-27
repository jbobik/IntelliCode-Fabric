"""
Fine-tuning engine v3 — QLoRA on your codebase.

Improvements v3:
- Extended training params (learning_rate, batch_size, lora_r, lora_alpha, etc.) 
  can be passed from UI, with sensible defaults
- Fixed timeout issue: now runs as background task, status polled via /fine-tune/status
- Unique adapter names with timestamp → ALL versions preserved
- Better error handling and progress reporting
- use_reentrant=False to suppress torch warning
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_fine_tune_status = {
    "running": False,
    "progress": 0,
    "epoch": 0,
    "total_epochs": 0,
    "loss": 0.0,
    "message": "Idle",
    "examples_count": 0,
    "strategy_breakdown": {},
    "adapter_path": None,
}


class FineTuner:
    def __init__(self, config: dict):
        self.config = config
        self.ft_config = config.get("fine_tuning", {})
        self.models_dir = Path(__file__).parent.parent / "models"
        self.data_dir = Path(__file__).parent.parent / "data"
        self.adapter_dir = Path(__file__).parent.parent / self.ft_config.get("adapter_dir", "models/adapters")

    @staticmethod
    def get_status() -> dict:
        return _fine_tune_status.copy()

    @staticmethod
    def list_adapters() -> list[dict]:
        """List ALL available fine-tuned adapters (not just last one)."""
        adapter_base = Path(__file__).parent.parent / "models" / "adapters"
        adapters = []
        if adapter_base.exists():
            for d in sorted(adapter_base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if d.is_dir() and (d / "adapter_config.json").exists():
                    meta_path = d / "training_meta.json"
                    meta = {}
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text())
                        except Exception:
                            pass
                    adapters.append({
                        "id": d.name,
                        "path": str(d),
                        "model_id": meta.get("model_id", "unknown"),
                        "examples": meta.get("num_examples", 0),
                        "epochs": meta.get("epochs", 0),
                        "project": meta.get("project_path", ""),
                        "project_name": meta.get("project_name", ""),
                        "created_at": meta.get("created_at", ""),
                        "learning_rate": meta.get("learning_rate", ""),
                        "lora_r": meta.get("lora_r", ""),
                    })
        return adapters

    async def fine_tune(self, project_path: str, model_id: str, epochs: int = 3,
                        strategies: Optional[list[str]] = None,
                        override_params: Optional[dict] = None) -> dict:
        global _fine_tune_status

        if _fine_tune_status["running"]:
            return {"status": "error", "message": "Fine-tuning already in progress"}

        if strategies is None:
            strategies = self.ft_config.get("strategies", [
                "docstring_to_impl", "comment_to_code", "file_completion", "function_signature"
            ])

        # Merge override params with defaults
        effective_params = {
            "learning_rate": self.ft_config.get("learning_rate", 2e-4),
            "batch_size": self.ft_config.get("batch_size", 2),
            "gradient_accumulation_steps": self.ft_config.get("gradient_accumulation_steps", 4),
            "lora_r": self.ft_config.get("lora_r", 16),
            "lora_alpha": self.ft_config.get("lora_alpha", 32),
            "lora_dropout": self.ft_config.get("lora_dropout", 0.05),
            "max_seq_length": self.ft_config.get("max_seq_length", 1024),
            "warmup_ratio": self.ft_config.get("warmup_ratio", 0.03),
        }
        if override_params:
            for k, v in override_params.items():
                if v is not None and k in effective_params:
                    effective_params[k] = v

        try:
            _fine_tune_status = {
                "running": True,
                "progress": 0,
                "epoch": 0,
                "total_epochs": epochs,
                "loss": 0.0,
                "message": "Scanning project for training data...",
                "examples_count": 0,
                "strategy_breakdown": {},
                "adapter_path": None,
            }

            logger.info(f"Fine-tuning on {project_path} with strategies: {strategies}")
            logger.info(f"Effective params: {effective_params}")

            # Step 1: Extract training data
            dataset, breakdown = await self._prepare_dataset(project_path, strategies)

            _fine_tune_status["examples_count"] = len(dataset)
            _fine_tune_status["strategy_breakdown"] = breakdown
            _fine_tune_status["progress"] = 10
            _fine_tune_status["message"] = (
                f"Extracted {len(dataset)} examples. "
                f"Breakdown: {', '.join(f'{k}:{v}' for k,v in breakdown.items())}"
            )

            min_examples = self.ft_config.get("min_examples", 10)
            if len(dataset) < min_examples:
                msg = (
                    f"Not enough training data ({len(dataset)} examples, need {min_examples}). "
                    f"Add more docstrings/comments to your code."
                )
                _fine_tune_status.update({"running": False, "message": msg})
                return {"status": "error", "message": msg}

            # Step 2: Find model info (check built-in AND custom models)
            model_info = None
            all_models = list(self.config["models"]["available"])
            # Load custom models list
            custom_path = Path(__file__).parent.parent / "data" / "custom_models.json"
            if custom_path.exists():
                try:
                    import json as _json
                    all_models += _json.loads(custom_path.read_text())
                except Exception:
                    pass
            for m in all_models:
                if m["id"] == model_id:
                    model_info = m
                    break
            if not model_info:
                # Also try matching by current loaded model
                raise ValueError(f"Model {model_id} not found")

            _fine_tune_status["message"] = f"Loading {model_info['name']} for fine-tuning..."
            _fine_tune_status["progress"] = 15

            # Step 3: Train
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: self._fine_tune_sync(
                    model_info, dataset, epochs, project_path, effective_params
                )
            )

            _fine_tune_status.update({
                "running": False,
                "progress": 100,
                "message": f"✅ Fine-tuning complete! Adapter saved to: {result.get('adapter_path', '')}",
                "adapter_path": result.get("adapter_path"),
            })

            return result

        except Exception as e:
            _fine_tune_status.update({"running": False, "message": f"❌ Error: {str(e)}"})
            logger.error(f"Fine-tuning error: {e}", exc_info=True)
            raise

    # ─────────────────────────────────────────────
    #  DATA EXTRACTION (same as before, kept for brevity)
    # ─────────────────────────────────────────────

    async def _prepare_dataset(self, project_path: str,
                                strategies: list[str]) -> tuple[list[dict], dict]:
        dataset = []
        breakdown: dict[str, int] = {s: 0 for s in strategies}

        project = Path(project_path)
        supported_ext = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cs", ".rb"}
        ignore_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", "target"}

        files = []
        for f in project.rglob("*"):
            if f.suffix not in supported_ext:
                continue
            if any(ig in f.parts for ig in ignore_dirs):
                continue
            if f.stat().st_size > 200_000:
                continue
            files.append(f)

        logger.info(f"Found {len(files)} source files")

        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore").strip()
                if len(content) < 50:
                    continue
                rel_path = str(f.relative_to(project))

                if "docstring_to_impl" in strategies:
                    ex = self._extract_docstring_examples(content, rel_path, f.suffix)
                    dataset.extend(ex)
                    breakdown["docstring_to_impl"] += len(ex)

                if "comment_to_code" in strategies:
                    ex = self._extract_comment_examples(content, rel_path, f.suffix)
                    dataset.extend(ex)
                    breakdown["comment_to_code"] += len(ex)

                if "file_completion" in strategies and len(content) > 200:
                    ex = self._extract_file_completion(content, rel_path)
                    dataset.extend(ex)
                    breakdown["file_completion"] += len(ex)

                if "function_signature" in strategies:
                    ex = self._extract_signature_examples(content, rel_path, f.suffix)
                    dataset.extend(ex)
                    breakdown["function_signature"] += len(ex)

                if "test_to_impl" in strategies:
                    ex = self._extract_test_examples(content, rel_path, f.suffix)
                    dataset.extend(ex)
                    breakdown["test_to_impl"] += len(ex)

            except Exception as e:
                logger.warning(f"Error extracting from {f}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for item in dataset:
            key = item["text"][:100]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        logger.info(f"Total unique examples: {len(unique)} | breakdown: {breakdown}")
        return unique, breakdown

    def _extract_docstring_examples(self, content, file_path, ext):
        examples = []
        if ext == ".py":
            pattern = r'(def\s+\w+[^:]*:\s*\n\s*"""[\s\S]*?""")([\s\S]*?)(?=\ndef\s|\nclass\s|\nasync\s+def\s|\Z)'
            for m in re.finditer(pattern, content):
                sig_doc = m.group(1).strip()
                body = m.group(2).strip()
                if len(body) > 20:
                    examples.append({"text": f"# {file_path}\n{sig_doc}\n{body[:800]}"})
        elif ext in (".js", ".ts", ".tsx", ".jsx"):
            pattern = r'(/\*\*[\s\S]*?\*/)\s*\n\s*((?:export\s+)?(?:async\s+)?(?:function|const|class)\s+\w+[\s\S]*?\{[\s\S]*?)(?=\n(?:export|function|class|/\*\*)|\Z)'
            for m in re.finditer(pattern, content):
                jsdoc = m.group(1).strip()
                impl = m.group(2).strip()
                if len(impl) > 20:
                    examples.append({"text": f"// {file_path}\n{jsdoc}\n{impl[:800]}"})
        elif ext == ".java":
            pattern = r'(/\*\*[\s\S]*?\*/)\s*\n\s*((?:public|private|protected)[\s\S]*?\{[\s\S]*?)(?=\n\s*(?:public|private|protected|/\*\*)|\Z)'
            for m in re.finditer(pattern, content):
                javadoc = m.group(1).strip()
                impl = m.group(2).strip()
                if len(impl) > 20:
                    examples.append({"text": f"// {file_path}\n{javadoc}\n{impl[:800]}"})
        return examples

    def _extract_comment_examples(self, content, file_path, ext):
        examples = []
        lines = content.split('\n')
        prefixes = {'#'} if ext == '.py' else {'//'}
        i = 0
        while i < len(lines) - 1:
            line = lines[i].strip()
            is_comment = any(line.startswith(p) for p in prefixes) and len(line) > 15
            if is_comment:
                code_lines = []
                j = i + 1
                while j < min(len(lines), i + 25):
                    nl = lines[j].strip()
                    if not nl:
                        j += 1; continue
                    if any(nl.startswith(p) for p in prefixes):
                        break
                    code_lines.append(lines[j])
                    j += 1
                if len(code_lines) >= 2:
                    code_block = '\n'.join(code_lines)
                    if len(code_block) > 30:
                        examples.append({"text": f"# {file_path}\n{line}\n{code_block[:500]}"})
                i = j
            else:
                i += 1
        return examples

    def _extract_file_completion(self, content, file_path):
        lines = content.split('\n')
        if len(lines) < 15:
            return []
        examples = []
        for frac in [0.33, 0.5, 0.67]:
            split = int(len(lines) * frac)
            prefix = '\n'.join(lines[:split])
            suffix = '\n'.join(lines[split:split + 30])
            if len(suffix) > 50:
                examples.append({"text": f"# File: {file_path} (continuation)\n{prefix[-600:]}\n{suffix}"})
        return examples

    def _extract_signature_examples(self, content, file_path, ext):
        examples = []
        if ext == ".py":
            pattern = r'((?:async\s+)?def\s+\w+\([^)]*\)(?:\s*->\s*\S+)?:)([\s\S]*?)(?=\n(?:async\s+)?def\s|\nclass\s|\Z)'
            for m in re.finditer(pattern, content):
                sig = m.group(1).strip()
                body = m.group(2).strip()
                if len(body) > 30:
                    examples.append({"text": f"# {file_path}\n{sig}\n{body[:600]}"})
        elif ext in (".ts", ".js"):
            pattern = r'((?:export\s+)?(?:async\s+)?function\s+\w+\([^)]*\)(?::\s*\S+)?)\s*\{([\s\S]*?)(?=\n(?:export\s+)?(?:async\s+)?function|\nclass|\Z)'
            for m in re.finditer(pattern, content):
                sig = m.group(1).strip()
                body = m.group(2).strip()
                if len(body) > 30:
                    examples.append({"text": f"// {file_path}\n{sig} {{\n{body[:600]}"})
        return examples

    def _extract_test_examples(self, content, file_path, ext):
        examples = []
        test_indicators = ["test_", "it(", "describe(", "@Test", "func Test"]
        if not any(ind in content for ind in test_indicators):
            return examples
        lines = content.split('\n')
        test_start_patterns = [
            r'def test_\w+', r'it\([\'"]', r'test\([\'"]', r'describe\([\'"]'
        ]
        for i, line in enumerate(lines):
            for pat in test_start_patterns:
                if re.match(r'\s*' + pat, line):
                    block = '\n'.join(lines[i:i + 30])
                    if len(block) > 50:
                        examples.append({"text": f"# {file_path} (test)\n{block[:600]}"})
                    break
        return examples[:10]

    # ─────────────────────────────────────────────
    #  TRAINING
    # ─────────────────────────────────────────────

    def _fine_tune_sync(self, model_info: dict, dataset: list[dict],
                        epochs: int, project_path: str, params: dict) -> dict:
        global _fine_tune_status
        import torch
        import json
        from datetime import datetime

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
            from peft import LoraConfig, get_peft_model
            from datasets import Dataset
        except ImportError as e:
            raise RuntimeError(f"Missing packages. Run: pip install peft trl datasets\nMissing: {e}")

        repo = model_info["repo"]
        model_id = model_info["id"]
        project_name = Path(project_path).name

        # UNIQUE adapter name with timestamp → all versions preserved
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        adapter_name = f"{model_id}__{project_name}__{timestamp}"
        adapter_path = str(self.adapter_dir / adapter_name)
        Path(adapter_path).mkdir(parents=True, exist_ok=True)

        _fine_tune_status["message"] = "Loading tokenizer..."
        _fine_tune_status["progress"] = 20

        tokenizer = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        _fine_tune_status["message"] = "Loading base model..."
        _fine_tune_status["progress"] = 25

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
                    repo, quantization_config=quant_config,
                    device_map="auto", trust_remote_code=True,
                )
                model = prepare_model_for_kbit_training(model)
            except ImportError:
                model = AutoModelForCausalLM.from_pretrained(
                    repo, trust_remote_code=True, torch_dtype=torch.float16,
                )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                repo, trust_remote_code=True, torch_dtype=torch.float32,
            )

        # Suppress use_reentrant warning
        if hasattr(torch.utils.checkpoint, 'checkpoint'):
            import functools
            original_checkpoint = torch.utils.checkpoint.checkpoint
            torch.utils.checkpoint.checkpoint = functools.partial(
                original_checkpoint, use_reentrant=False
            )

        _fine_tune_status["message"] = "Applying LoRA adapters..."
        _fine_tune_status["progress"] = 30

        target_modules = self._find_target_modules(model)
        logger.info(f"LoRA target modules: {target_modules}")

        lora_config = LoraConfig(
            r=params["lora_r"],
            lora_alpha=params["lora_alpha"],
            lora_dropout=params["lora_dropout"],
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=target_modules,
        )
        model = get_peft_model(model, lora_config)

        trainable, total = 0, 0
        for p in model.parameters():
            total += p.numel()
            if p.requires_grad:
                trainable += p.numel()
        logger.info(f"LoRA: trainable={trainable:,} / total={total:,} ({100*trainable/total:.3f}%)")

        _fine_tune_status["message"] = "Preparing dataset..."
        _fine_tune_status["progress"] = 35

        formatted = []
        for item in dataset:
            text = item["text"]
            if not text.endswith(tokenizer.eos_token):
                text += tokenizer.eos_token
            formatted.append({"text": text})

        hf_dataset = Dataset.from_list(formatted)

        _fine_tune_status["message"] = "Training in progress..."
        _fine_tune_status["progress"] = 40

        class ProgressCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if state.global_step > 0 and logs:
                    progress = min(95, 40 + int(55 * state.global_step / max(state.max_steps, 1)))
                    _fine_tune_status.update({
                        "progress": progress,
                        "epoch": int(state.epoch or 0),
                        "loss": round(logs.get("loss", 0), 4),
                        "message": (
                            f"Training... step {state.global_step}/{state.max_steps} | "
                            f"loss: {logs.get('loss', 0):.4f} | "
                            f"epoch: {state.epoch:.2f}/{epochs}"
                        ),
                    })

        common_args = dict(
            output_dir=adapter_path + "_checkpoints",
            num_train_epochs=epochs,
            per_device_train_batch_size=params["batch_size"],
            gradient_accumulation_steps=params["gradient_accumulation_steps"],
            learning_rate=params["learning_rate"],
            warmup_ratio=params["warmup_ratio"],
            logging_steps=5,
            save_strategy="epoch",
            fp16=(device == "cuda"),
            optim="adamw_torch",
            report_to="none",
            max_grad_norm=0.3,
            lr_scheduler_type="cosine",
            remove_unused_columns=False,
        )

        max_seq_length = params["max_seq_length"]

        # Try multiple trl API versions
        trainer = None
        last_error = None

        if trainer is None:
            try:
                from trl import SFTConfig, SFTTrainer
                training_args = SFTConfig(**common_args, dataset_text_field="text")
                trainer = SFTTrainer(
                    model=model, train_dataset=hf_dataset, args=training_args,
                    processing_class=tokenizer, max_seq_length=max_seq_length,
                    callbacks=[ProgressCallback()],
                )
            except TypeError as e:
                last_error = e; trainer = None

        if trainer is None:
            try:
                from trl import SFTConfig, SFTTrainer
                training_args = SFTConfig(**common_args, dataset_text_field="text", max_seq_length=max_seq_length)
                trainer = SFTTrainer(
                    model=model, train_dataset=hf_dataset, args=training_args,
                    processing_class=tokenizer, callbacks=[ProgressCallback()],
                )
            except TypeError as e:
                last_error = e; trainer = None

        if trainer is None:
            try:
                from trl import SFTTrainer
                from transformers import TrainingArguments
                training_args = TrainingArguments(**common_args)
                trainer = SFTTrainer(
                    model=model, train_dataset=hf_dataset, args=training_args,
                    tokenizer=tokenizer, dataset_text_field="text",
                    max_seq_length=max_seq_length, callbacks=[ProgressCallback()],
                )
            except TypeError as e:
                last_error = e; trainer = None

        if trainer is None:
            from transformers import TrainingArguments, Trainer
            training_args = TrainingArguments(**common_args)
            def tokenize_fn(examples):
                return tokenizer(examples["text"], truncation=True, max_length=max_seq_length, padding="max_length")
            tokenized_dataset = hf_dataset.map(tokenize_fn, batched=True, remove_columns=["text"])
            tokenized_dataset = tokenized_dataset.map(lambda x: {"labels": x["input_ids"]}, batched=True)
            trainer = Trainer(
                model=model, train_dataset=tokenized_dataset,
                args=training_args, callbacks=[ProgressCallback()],
            )

        logger.info(f"Starting training: {len(formatted)} examples, {epochs} epochs")
        trainer.train()

        _fine_tune_status["message"] = "Saving adapter..."
        _fine_tune_status["progress"] = 97

        model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)

        meta = {
            "model_id": model_id,
            "model_name": model_info["name"],
            "project_path": project_path,
            "project_name": project_name,
            "num_examples": len(formatted),
            "epochs": epochs,
            "trainable_params": trainable,
            "total_params": total,
            "learning_rate": params["learning_rate"],
            "batch_size": params["batch_size"],
            "lora_r": params["lora_r"],
            "lora_alpha": params["lora_alpha"],
            "max_seq_length": params["max_seq_length"],
            "created_at": datetime.now().isoformat(),
        }
        (Path(adapter_path) / "training_meta.json").write_text(json.dumps(meta, indent=2))

        logger.info(f"Adapter saved to {adapter_path}")
        return {
            "status": "ok",
            "adapter_path": adapter_path,
            "adapter_name": adapter_name,
            "num_examples": len(formatted),
            "epochs": epochs,
            "trainable_params": trainable,
            "total_params": total,
        }

    def _find_target_modules(self, model) -> list[str]:
        linear_names = set()
        for name, module in model.named_modules():
            try:
                from torch.nn import Linear
                if isinstance(module, Linear):
                    parts = name.split('.')
                    linear_names.add(parts[-1])
            except Exception:
                pass

        preferred = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        found = [m for m in preferred if m in linear_names]
        if found:
            return found

        for pattern in [["query", "key", "value"], ["c_attn", "c_proj"]]:
            if all(m in linear_names for m in pattern):
                return pattern

        return list(linear_names)[:4] if linear_names else ["q_proj", "v_proj"]