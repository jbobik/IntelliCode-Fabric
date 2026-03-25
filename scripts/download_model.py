#!/usr/bin/env python3
"""
Download models for AI Code Partner
"""

import argparse
import sys
import yaml
from pathlib import Path
from huggingface_hub import snapshot_download


def main():
    config_path = Path(__file__).parent.parent / "backend" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    available = config["models"]["available"]

    parser = argparse.ArgumentParser(description="Download models for AI Code Partner")
    parser.add_argument(
        "--model",
        choices=[m["id"] for m in available],
        help="Model ID to download",
    )
    parser.add_argument("--list", action="store_true", help="List available models")

    args = parser.parse_args()

    if args.list or not args.model:
        print("\nAvailable models:")
        print("-" * 70)
        for m in available:
            models_dir = Path(__file__).parent.parent / "models" / m["id"]
            status = "✓ Downloaded" if models_dir.exists() and any(models_dir.iterdir()) if models_dir.exists() else False else "Not downloaded"
            print(f"  {m['id']:30s} | {m['ram_required']:6s} | {status}")
            print(f"    {m['description']}")
            print()
        if not args.model:
            return

    model_info = next(m for m in available if m["id"] == args.model)
    output_dir = Path(__file__).parent.parent / "models" / model_info["id"]

    print(f"\nDownloading {model_info['name']}...")
    print(f"  Repo: {model_info['repo']}")
    print(f"  RAM required: {model_info['ram_required']}")
    print(f"  Destination: {output_dir}")
    print()

    snapshot_download(
        repo_id=model_info["repo"],
        local_dir=str(output_dir),
        local_dir_use_symlinks=False,
    )

    print(f"\n✓ Model {model_info['id']} downloaded successfully!")


if __name__ == "__main__":
    main()