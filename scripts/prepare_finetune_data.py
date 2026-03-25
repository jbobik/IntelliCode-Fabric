#!/usr/bin/env python3
"""
Prepare fine-tuning data from a project
"""

import argparse
import json
import re
from pathlib import Path


def extract_examples(project_path: str) -> list[dict]:
    """Extract training examples from project"""
    project = Path(project_path)
    examples = []

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

            # Function-level examples
            if f.suffix == ".py":
                pattern = r'(def\s+\w+.*?:\s*\n\s*""".*?""")\s*\n(.*?)(?=\ndef\s|\nclass\s|\Z)'
                for match in re.finditer(pattern, content, re.DOTALL):
                    sig = match.group(1).strip()
                    impl = match.group(2).strip()
                    if len(impl) > 20:
                        examples.append({
                            "instruction": f"Implement the following function in {rel_path}",
                            "input": sig,
                            "output": impl[:800],
                        })

            # Completion-style examples
            lines = content.split('\n')
            if len(lines) > 10:
                mid = len(lines) // 2
                examples.append({
                    "instruction": f"Continue the code in {rel_path}",
                    "input": '\n'.join(lines[:mid]),
                    "output": '\n'.join(lines[mid:mid + 20]),
                })

        except Exception as e:
            print(f"Warning: {f}: {e}")

    return examples


def main():
    parser = argparse.ArgumentParser(description="Prepare fine-tuning data")
    parser.add_argument("project_path", help="Path to project")
    parser.add_argument("--output", default="data/finetune_data.jsonl", help="Output file")

    args = parser.parse_args()

    print(f"Extracting examples from {args.project_path}...")
    examples = extract_examples(args.project_path)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Extracted {len(examples)} examples → {output_path}")


if __name__ == "__main__":
    main()