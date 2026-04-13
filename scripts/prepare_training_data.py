from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return load_csv(path)
    return load_jsonl(path)


def format_prompt(instruction: str, context: str) -> str:
    instruction = instruction.strip()
    context = context.strip()
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def build_sft_rows(raw_rows: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for row in raw_rows:
        instruction = str(row.get("instruction") or row.get("prompt") or "").strip()
        context = str(row.get("context", "")).strip()
        response = str(row.get("response") or row.get("output") or "").strip()
        if not instruction or not response:
            continue
        prompt = format_prompt(instruction, context)
        prepared.append(
            {
                "instruction": instruction,
                "context": context,
                "response": response,
                "text": prompt + response,
            }
        )
    return prepared


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SFT dataset from Dolly-like JSONL")
    parser.add_argument("--input", default="data/raw/dolly_sample.jsonl")
    parser.add_argument("--output", default="data/processed/sft_dataset.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    raw = load_rows(input_path)
    if args.limit and args.limit > 0:
        raw = raw[: args.limit]

    prepared = build_sft_rows(raw)
    write_jsonl(output_path, prepared)

    print(f"Prepared {len(prepared)} rows -> {output_path}")


if __name__ == "__main__":
    main()
