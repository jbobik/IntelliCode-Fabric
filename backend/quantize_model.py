"""
Model quantization script — GPTQ and bitsandbytes quantization
"""

import argparse
import logging
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


def quantize_gptq(model_path: str, output_path: str, bits: int = 4):
    """Quantize model using GPTQ"""
    from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig

    quantize_config = BaseQuantizeConfig(
        bits=bits,
        group_size=128,
        desc_act=False,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoGPTQForCausalLM.from_pretrained(
        model_path,
        quantize_config=quantize_config,
        trust_remote_code=True,
    )

    # Calibration data
    calibration_data = [
        tokenizer(
            "def hello_world():\n    print('Hello, World!')\n\nclass Calculator:\n    def add(self, a, b):\n        return a + b",
            return_tensors="pt",
        )
    ]

    logger.info("Quantizing model...")
    model.quantize(calibration_data)

    logger.info(f"Saving quantized model to {output_path}")
    model.save_quantized(output_path)
    tokenizer.save_pretrained(output_path)

    logger.info("Quantization complete!")


def quantize_bnb(model_path: str, output_path: str, bits: int = 4):
    """Quantize model using bitsandbytes (4-bit or 8-bit)"""
    from transformers import BitsAndBytesConfig

    if bits == 4:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    else:
        quant_config = BitsAndBytesConfig(load_in_8bit=True)

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )

    logger.info(f"Saving to {output_path}")
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)
    logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantize a model")
    parser.add_argument("--model", required=True, help="Model path or HF repo")
    parser.add_argument("--output", required=True, help="Output path")
    parser.add_argument("--bits", type=int, default=4, choices=[4, 8])
    parser.add_argument("--method", default="bnb", choices=["gptq", "bnb"])

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.method == "gptq":
        quantize_gptq(args.model, args.output, args.bits)
    else:
        quantize_bnb(args.model, args.output, args.bits)