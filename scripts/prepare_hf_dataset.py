from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset


def format_prompt(instruction: str, context: str) -> str:
    instruction = instruction.strip()
    context = context.strip()
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def to_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def cyrillic_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    return cyr / len(letters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SFT jsonl from Hugging Face dataset")
    parser.add_argument("--dataset", default="databricks/databricks-dolly-15k")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output", default="data/processed/sft_dataset_hf.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--instruction-field", default="instruction")
    parser.add_argument("--context-field", default="context")
    parser.add_argument("--response-field", default="response")
    parser.add_argument("--min-cyrillic-ratio", type=float, default=0.0)
    args = parser.parse_args()

    ds = load_dataset(args.dataset, split=args.split)
    if args.limit and args.limit > 0:
        ds = ds.select(range(min(args.limit, len(ds))))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for row in ds:
            instruction = to_text(row.get(args.instruction_field, "")).strip()
            context = to_text(row.get(args.context_field, "")).strip()
            response = to_text(row.get(args.response_field, "")).strip()

            if not instruction or not response:
                continue

            joined = f"{instruction} {context} {response}"
            if cyrillic_ratio(joined) < args.min_cyrillic_ratio:
                continue

            text = format_prompt(instruction, context) + response
            payload = {
                "instruction": instruction,
                "context": context,
                "response": response,
                "text": text,
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            written += 1

    print(f"Prepared {written} rows -> {output_path}")


if __name__ == "__main__":
    main()
