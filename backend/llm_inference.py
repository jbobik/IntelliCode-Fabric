"""
Local LLM Inference Engine — loads and runs models with quantization
"""

import asyncio
import gc
import logging
import os
from pathlib import Path
from typing import AsyncGenerator, Optional

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
)
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
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.models_dir = Path(__file__).parent.parent / "models"
        self.models_dir.mkdir(exist_ok=True)
        self._lock = asyncio.Lock()
        logger.info(f"LLM Inference initialized. Device: {self.device}")

    def is_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def unload(self):
        """Unload current model from memory"""
        logger.info("Unloading model...")
        if self.model is not None:
            del self.model
        if self.tokenizer is not None:
            del self.tokenizer
        self.model = None
        self.tokenizer = None
        self.current_model_id = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Model unloaded")

    # ──────────────────────────────────────────────
    #  DOWNLOAD
    # ──────────────────────────────────────────────

    async def download_model(self, model_info: dict) -> str:
        """Download model from HuggingFace Hub"""
        model_id = model_info["id"]
        repo = model_info["repo"]
        save_path = str(self.models_dir / model_id)

        logger.info(f"Downloading model {repo} to {save_path}")

        loop = asyncio.get_event_loop()

        def _do_download():
            snapshot_download(
                repo_id=repo,
                local_dir=save_path,
                local_dir_use_symlinks=False,
            )
            logger.info(f"Model downloaded to {save_path}")
            return save_path

        result = await loop.run_in_executor(None, _do_download)
        return result

    # ──────────────────────────────────────────────
    #  LOAD MODEL
    # ──────────────────────────────────────────────

    async def load_model(self, model_info: dict):
        """Load a model with optional quantization"""
        async with self._lock:
            if self.is_loaded():
                self.unload()

            model_id = model_info["id"]
            repo = model_info["repo"]
            quantization = model_info.get("quantization", "4bit")

            # Check local first
            local_path = self.models_dir / model_id
            if local_path.exists() and any(local_path.iterdir()):
                model_path = str(local_path)
                logger.info(f"Loading model from local: {model_path}")
            else:
                model_path = repo
                logger.info(f"Loading model from HuggingFace: {repo}")

            logger.info(f"Device: {self.device}, Quantization: {quantization}")

            loop = asyncio.get_event_loop()

            def _do_load():
                self._load_model_sync(model_path, quantization)

            await loop.run_in_executor(None, _do_load)

            self.current_model_id = model_id
            logger.info(f"Model {model_id} loaded successfully")

    def _load_model_sync(self, model_path: str, quantization: str):
        """Synchronous model loading with fallback"""

        # ── Tokenizer ──
        logger.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            padding_side="left",
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # ── Model ──
        loaded = False

        # Attempt 1: 4-bit quantization (CUDA + bitsandbytes)
        if quantization == "4bit" and self.device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                logger.info("Attempting 4-bit quantized loading...")
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    quantization_config=quant_config,
                    device_map="auto",
                    trust_remote_code=True,
                    torch_dtype=torch.float16,
                )
                loaded = True
                logger.info("Model loaded with 4-bit quantization")
            except ImportError:
                logger.warning("bitsandbytes not installed, skipping 4-bit quantization")
            except Exception as e:
                logger.warning(f"4-bit loading failed: {e}")

        # Attempt 2: 8-bit quantization (CUDA + bitsandbytes)
        if not loaded and quantization in ("4bit", "8bit") and self.device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                logger.info("Attempting 8-bit quantized loading...")
                quant_config = BitsAndBytesConfig(load_in_8bit=True)
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    quantization_config=quant_config,
                    device_map="auto",
                    trust_remote_code=True,
                )
                loaded = True
                logger.info("Model loaded with 8-bit quantization")
            except ImportError:
                logger.warning("bitsandbytes not installed, skipping 8-bit quantization")
            except Exception as e:
                logger.warning(f"8-bit loading failed: {e}")

        # Attempt 3: FP16 on CUDA (no quantization)
        if not loaded and self.device == "cuda":
            try:
                logger.info("Loading model in FP16 on CUDA...")
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    device_map="auto",
                    trust_remote_code=True,
                    torch_dtype=torch.float16,
                    low_cpu_mem_usage=True,
                )
                loaded = True
                logger.info("Model loaded in FP16 on CUDA")
            except Exception as e:
                logger.warning(f"FP16 CUDA loading failed: {e}")

        # Attempt 4: CPU FP32 (ultimate fallback)
        if not loaded:
            logger.info("Loading model in FP32 on CPU (this will be slow)...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
            logger.info("Model loaded in FP32 on CPU")

        self.model.eval()
        logger.info(f"Model ready on {next(self.model.parameters()).device}")

    # ──────────────────────────────────────────────
    #  GENERATE (non-streaming)
    # ──────────────────────────────────────────────

    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text (non-streaming)"""
        if not self.is_loaded():
            raise RuntimeError("No model loaded")

        loop = asyncio.get_event_loop()

        def _do_generate():
            return self._generate_sync(prompt, **kwargs)

        result = await loop.run_in_executor(None, _do_generate)
        return result

    def _generate_sync(self, prompt: str, **kwargs) -> str:
        """Synchronous generation"""
        max_input_length = 4096

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=max_input_length,
        )
        input_device = next(self.model.parameters()).device
        inputs = {k: v.to(input_device) for k, v in inputs.items()}

        max_new_tokens = kwargs.get(
            "max_new_tokens", self.gen_config.get("max_new_tokens", 2048)
        )
        temperature = kwargs.get(
            "temperature", self.gen_config.get("temperature", 0.2)
        )
        top_p = kwargs.get("top_p", self.gen_config.get("top_p", 0.95))

        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "top_p": top_p,
            "top_k": self.gen_config.get("top_k", 50),
            "repetition_penalty": self.gen_config.get("repetition_penalty", 1.1),
            "pad_token_id": self.tokenizer.pad_token_id,
        }

        # Temperature handling
        if temperature > 0.01:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True
        else:
            gen_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self.model.generate(**gen_kwargs)

        # Decode only new tokens
        input_length = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_length:]
        result = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        return result.strip()

    # ──────────────────────────────────────────────
    #  GENERATE (streaming)
    # ──────────────────────────────────────────────

    async def generate_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream generation token by token"""
        if not self.is_loaded():
            raise RuntimeError("No model loaded")

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        max_input_length = 4096
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=max_input_length,
        )
        input_device = next(self.model.parameters()).device
        inputs = {k: v.to(input_device) for k, v in inputs.items()}

        max_new_tokens = kwargs.get(
            "max_new_tokens", self.gen_config.get("max_new_tokens", 2048)
        )
        temperature = kwargs.get(
            "temperature", self.gen_config.get("temperature", 0.2)
        )

        gen_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_new_tokens,
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