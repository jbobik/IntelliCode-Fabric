"""
Local LLM Inference Engine — loads models with quantization + LoRA adapter support.
"""

import asyncio
import gc
import logging
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread
from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)


class LLMInference:
    def __init__(self, config: dict):
        self.config = config
        self.gen_config = config.get("generation", {})
        self.model = None
        self.tokenizer = None
        self.current_model_id: Optional[str] = None
        self.active_adapter: Optional[str] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.models_dir = Path(__file__).parent.parent / "models"
        self.models_dir.mkdir(exist_ok=True)
        self._lock = asyncio.Lock()
        logger.info(f"LLMInference initialized. Device: {self.device}")

    def is_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def unload(self):
        logger.info("Unloading model...")
        del self.model
        del self.tokenizer
        self.model = None
        self.tokenizer = None
        self.current_model_id = None
        self.active_adapter = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ─── DOWNLOAD ────────────────────────────────────────────────

    async def download_model(self, model_info: dict,
                              progress_callback: Optional[Callable] = None) -> str:
        model_id = model_info["id"]
        repo = model_info["repo"]
        save_path = str(self.models_dir / model_id)

        logger.info(f"Downloading {repo} → {save_path}")
        loop = asyncio.get_event_loop()

        def _do_download():
            snapshot_download(
                repo_id=repo,
                local_dir=save_path,
                local_dir_use_symlinks=False,
                tqdm_class=None,
            )
            return save_path

        result = await loop.run_in_executor(None, _do_download)
        return result

    # ─── LOAD ──────────────────────────────────────────────────

    async def load_model(self, model_info: dict, adapter_id: Optional[str] = None):
        async with self._lock:
            if self.is_loaded():
                self.unload()

            model_id = model_info["id"]
            repo = model_info["repo"]
            quantization = model_info.get("quantization", "4bit")

            local_path = self.models_dir / model_id
            model_path = str(local_path) if (local_path.exists() and any(local_path.iterdir())) else repo

            logger.info(f"Loading {model_id} from {model_path} | quant={quantization} | device={self.device}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._load_model_sync(model_path, quantization))

            # Load LoRA adapter if specified
            if adapter_id:
                await loop.run_in_executor(None, lambda: self._load_adapter(adapter_id))

            self.current_model_id = model_id
            logger.info(f"Model {model_id} ready" + (f" + adapter {adapter_id}" if adapter_id else ""))

    def _load_model_sync(self, model_path: str, quantization: str):
        logger.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True, padding_side="left",
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        loaded = False

        # 4-bit (CUDA + bitsandbytes)
        # Handle empty/none quantization
        if not quantization or quantization == "none":
            quantization = ""

        if quantization == "4bit" and self.device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4",
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path, quantization_config=quant_config,
                    device_map="auto", trust_remote_code=True, torch_dtype=torch.float16,
                )
                loaded = True
                logger.info("Loaded in 4-bit NF4")
            except Exception as e:
                logger.warning(f"4-bit load failed: {e}")

        # 8-bit fallback
        if not loaded and self.device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path, quantization_config=BitsAndBytesConfig(load_in_8bit=True),
                    device_map="auto", trust_remote_code=True,
                )
                loaded = True
                logger.info("Loaded in 8-bit")
            except Exception as e:
                logger.warning(f"8-bit load failed: {e}")

        # FP16 CUDA
        if not loaded and self.device == "cuda":
            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path, device_map="auto", trust_remote_code=True,
                    torch_dtype=torch.float16, low_cpu_mem_usage=True,
                )
                loaded = True
                logger.info("Loaded in FP16 on CUDA")
            except Exception as e:
                logger.warning(f"FP16 CUDA load failed: {e}")

        # CPU FP32
        if not loaded:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, trust_remote_code=True,
                torch_dtype=torch.float32, low_cpu_mem_usage=True,
            )
            logger.info("Loaded in FP32 on CPU")

        self.model.eval()

    def _load_adapter(self, adapter_id: str):
        """Load a LoRA adapter on top of the base model."""
        try:
            from peft import PeftModel
            adapter_base = Path(__file__).parent.parent / "models" / "adapters"
            adapter_path = str(adapter_base / adapter_id)
            logger.info(f"Loading adapter from {adapter_path}")
            self.model = PeftModel.from_pretrained(self.model, adapter_path)
            self.model.eval()
            self.active_adapter = adapter_id
            logger.info(f"Adapter {adapter_id} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load adapter {adapter_id}: {e}")
            self.active_adapter = None

    # ─── GENERATE ─────────────────────────────────────────────

    async def generate(self, prompt: str, **kwargs) -> str:
        if not self.is_loaded():
            raise RuntimeError("No model loaded")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._generate_sync(prompt, **kwargs))

    def _generate_sync(self, prompt: str, **kwargs) -> str:
        # Use model's max context length, fallback to 8192
        max_ctx = getattr(self.model.config, 'max_position_embeddings', 8192)
        max_ctx = min(max_ctx, 16384)  # cap at 16K to avoid OOM
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=max_ctx,
        )
        input_device = next(self.model.parameters()).device
        inputs = {k: v.to(input_device) for k, v in inputs.items()}

        max_new_tokens = kwargs.get("max_new_tokens", self.gen_config.get("max_new_tokens", 2048))
        temperature = kwargs.get("temperature", self.gen_config.get("temperature", 0.2))
        top_p = kwargs.get("top_p", self.gen_config.get("top_p", 0.95))

        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "top_p": top_p,
            "top_k": self.gen_config.get("top_k", 50),
            "repetition_penalty": self.gen_config.get("repetition_penalty", 1.1),
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        if temperature > 0.01:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True
        else:
            gen_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self.model.generate(**gen_kwargs)

        input_length = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_length:]
        return self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    # ─── STREAM ──────────────────────────────────────────────

    async def generate_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        if not self.is_loaded():
            raise RuntimeError("No model loaded")

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        max_ctx = getattr(self.model.config, 'max_position_embeddings', 8192)
        max_ctx = min(max_ctx, 16384)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_ctx)
        input_device = next(self.model.parameters()).device
        inputs = {k: v.to(input_device) for k, v in inputs.items()}

        temperature = kwargs.get("temperature", self.gen_config.get("temperature", 0.2))
        gen_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": kwargs.get("max_new_tokens", self.gen_config.get("max_new_tokens", 2048)),
            "top_p": self.gen_config.get("top_p", 0.95),
            "top_k": self.gen_config.get("top_k", 50),
            "repetition_penalty": self.gen_config.get("repetition_penalty", 1.1),
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        if temperature > 0.01:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True
        else:
            gen_kwargs["do_sample"] = False

        def _run():
            with torch.no_grad():
                self.model.generate(**gen_kwargs)

        thread = Thread(target=_run)
        thread.start()
        for text in streamer:
            yield text
            await asyncio.sleep(0)
        thread.join()