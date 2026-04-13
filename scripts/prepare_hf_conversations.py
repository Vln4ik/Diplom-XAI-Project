from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset


def to_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    return cyr / len(letters)


def format_prompt(instruction: str, context: str) -> str:
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def _parse_list_from_maybe_string(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except Exception:
            continue
    return []


def _message_role(msg: dict[str, Any]) -> str:
    role = str(msg.get("role", "")).strip().lower()
    if role in {"user", "human", "prompter", "question"}:
        return "user"
    if role in {"assistant", "gpt", "bot", "answer"}:
        return "assistant"
    return role


def _message_content(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if content is None:
        content = msg.get("text")
    return to_text(content)


def row_to_samples(
    row: dict[str, Any],
    max_pairs_per_dialog: int,
    min_cyrillic_ratio: float,
) -> list[dict[str, str]]:
    # direct instruction datasets fallback
    if {"instruction", "output"}.issubset(set(row.keys())):
        instruction = to_text(row.get("instruction"))
        context = to_text(row.get("input", row.get("context", "")))
        response = to_text(row.get("output"))
        joined = f"{instruction} {context} {response}"
        if instruction and response and cyrillic_ratio(joined) >= min_cyrillic_ratio:
            text = format_prompt(instruction, context) + response
            return [{"instruction": instruction, "context": context, "response": response, "text": text}]
        return []

    messages = _parse_list_from_maybe_string(row.get("messages"))
    if not messages:
        messages = _parse_list_from_maybe_string(row.get("conversation"))
    if not messages:
        messages = _parse_list_from_maybe_string(row.get("text"))
    if not messages:
        return []

    normalized: list[dict[str, str]] = []
    for msg in messages:
        role = _message_role(msg)
        content = _message_content(msg)
        if not content:
            continue
        normalized.append({"role": role, "content": content})

    results: list[dict[str, str]] = []
    for idx in range(1, len(normalized)):
        prev = normalized[idx - 1]
        curr = normalized[idx]
        if prev["role"] != "user" or curr["role"] != "assistant":
            continue

        instruction = prev["content"]
        response = curr["content"]
        if not instruction or not response:
            continue

        # Keep short conversation tail as context.
        tail = normalized[max(0, idx - 5) : idx - 1]
        context_parts = [f"{item['role']}: {item['content']}" for item in tail]
        context = "\n".join(context_parts)

        joined = f"{instruction} {context} {response}"
        if cyrillic_ratio(joined) < min_cyrillic_ratio:
            continue

        text = format_prompt(instruction, context) + response
        results.append(
            {
                "instruction": instruction,
                "context": context,
                "response": response,
                "text": text,
            }
        )
        if max_pairs_per_dialog > 0 and len(results) >= max_pairs_per_dialog:
            break

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SFT jsonl from HF conversation datasets")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit-rows", type=int, default=0, help="Limit input rows before conversion")
    parser.add_argument("--max-pairs-per-dialog", type=int, default=1)
    parser.add_argument("--min-cyrillic-ratio", type=float, default=0.3)
    args = parser.parse_args()

    ds = load_dataset(args.dataset, split=args.split)
    if args.limit_rows and args.limit_rows > 0:
        ds = ds.select(range(min(args.limit_rows, len(ds))))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for row in ds:
            samples = row_to_samples(
                row=row,
                max_pairs_per_dialog=args.max_pairs_per_dialog,
                min_cyrillic_ratio=args.min_cyrillic_ratio,
            )
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                written += 1

    print(f"Prepared {written} rows -> {output_path}")


if __name__ == "__main__":
    main()
