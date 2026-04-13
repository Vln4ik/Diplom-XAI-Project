from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


csv.field_size_limit(sys.maxsize)


USER_ROLES = {"user", "human", "prompter", "question"}
ASSISTANT_ROLES = {"assistant", "gpt", "bot", "answer"}


def to_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def normalize_role(role: object) -> str:
    value = to_text(role).lower()
    if value in USER_ROLES:
        return "user"
    if value in ASSISTANT_ROLES:
        return "assistant"
    return value


def format_prompt(instruction: str, context: str) -> str:
    if context:
        return f"### Инструкция:\n{instruction}\n\n### Контекст:\n{context}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction}\n\n### Ответ:\n"


def make_sample(instruction: str, context: str, response: str, source: str) -> dict[str, str]:
    instruction = to_text(instruction)
    context = to_text(context)
    response = to_text(response)
    return {
        "instruction": instruction,
        "context": context,
        "response": response,
        "text": format_prompt(instruction, context) + response,
        "source": source,
    }


def _parse_messages(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except Exception:
            continue

    # UltraChat Kaggle dump stores dicts line-by-line without commas: `}\n {`.
    fixed = re.sub(r"}\s*\n\s*{", "}, {", text)
    try:
        parsed = ast.literal_eval(fixed)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except Exception:
        pass

    return []


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k: (v or "") for k, v in row.items()}


def iter_dolly(path: Path, limit: int, min_response_chars: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if limit > 0 and len(rows) >= limit:
                break
            raw = json.loads(line)
            instruction = to_text(raw.get("instruction"))
            context = to_text(raw.get("context"))
            response = to_text(raw.get("response"))
            if not instruction or len(response) < min_response_chars:
                continue
            rows.append(make_sample(instruction, context, response, "kaggle-dolly15k"))
    return rows


def iter_openorca(path: Path, limit: int, min_response_chars: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in _read_csv(path):
        if limit > 0 and len(rows) >= limit:
            break
        instruction = to_text(raw.get("question"))
        context = to_text(raw.get("system_prompt"))
        response = to_text(raw.get("response"))
        if not instruction or len(response) < min_response_chars:
            continue
        rows.append(make_sample(instruction, context, response, "kaggle-openorca-small"))
    return rows


def iter_ultrachat(path: Path, limit: int, max_pairs_per_dialog: int, min_response_chars: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in _read_csv(path):
        if limit > 0 and len(rows) >= limit:
            break

        messages = _parse_messages(raw.get("messages"))
        if not messages:
            continue

        normalized: list[dict[str, str]] = []
        for msg in messages:
            role = normalize_role(msg.get("role"))
            content = to_text(msg.get("content", msg.get("text")))
            if not content:
                continue
            normalized.append({"role": role, "content": content})

        pair_count = 0
        for idx in range(1, len(normalized)):
            prev = normalized[idx - 1]
            cur = normalized[idx]
            if prev["role"] != "user" or cur["role"] != "assistant":
                continue
            if len(cur["content"]) < min_response_chars:
                continue

            tail = normalized[max(0, idx - 4) : idx - 1]
            context = "\n".join(f"{item['role']}: {item['content']}" for item in tail)
            rows.append(make_sample(prev["content"], context, cur["content"], "kaggle-ultrachat200k"))
            pair_count += 1

            if limit > 0 and len(rows) >= limit:
                break
            if max_pairs_per_dialog > 0 and pair_count >= max_pairs_per_dialog:
                break
    return rows


def iter_oasst(path: Path, limit: int, langs: set[str], min_response_chars: int) -> list[dict[str, str]]:
    raw_rows = list(_read_csv(path))
    by_id = {row.get("message_id", ""): row for row in raw_rows if row.get("message_id")}

    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if limit > 0 and len(rows) >= limit:
            break

        if normalize_role(row.get("role")) != "assistant":
            continue

        row_lang = to_text(row.get("lang"))
        if langs and row_lang not in langs:
            continue

        parent_id = to_text(row.get("parent_id"))
        parent = by_id.get(parent_id)
        if not parent:
            continue

        if normalize_role(parent.get("role")) != "user":
            continue

        instruction = to_text(parent.get("text"))
        response = to_text(row.get("text"))
        if not instruction or len(response) < min_response_chars:
            continue

        chain: list[tuple[str, str]] = []
        cursor_id = to_text(parent.get("parent_id"))
        while cursor_id:
            prev = by_id.get(cursor_id)
            if not prev:
                break
            role = normalize_role(prev.get("role"))
            text = to_text(prev.get("text"))
            if text:
                chain.append((role, text))
            cursor_id = to_text(prev.get("parent_id"))
            if len(chain) >= 4:
                break
        chain.reverse()
        context = "\n".join(f"{role}: {text}" for role, text in chain)

        rows.append(make_sample(instruction, context, response, "kaggle-oasst1"))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare mixed SFT dataset from Kaggle dumps")
    parser.add_argument("--dolly-path", default="data/raw/kaggle/dolly15k/databricks-dolly-15k.jsonl")
    parser.add_argument("--openorca-path", default="data/raw/kaggle/openorca_small/small_openorca.csv")
    parser.add_argument("--ultrachat-path", default="data/raw/kaggle/ultrachat200k/train_sft.csv")
    parser.add_argument("--oasst-path", default="data/raw/kaggle/oasst1/oasst1-train.csv")
    parser.add_argument("--output", default="data/processed/sft_kaggle_mix_v1.jsonl")
    parser.add_argument("--dolly-limit", type=int, default=3500)
    parser.add_argument("--openorca-limit", type=int, default=4000)
    parser.add_argument("--ultrachat-limit", type=int, default=3000)
    parser.add_argument("--oasst-limit", type=int, default=1500)
    parser.add_argument("--oasst-langs", default="ru,uk-UA,en")
    parser.add_argument("--max-pairs-per-dialog", type=int, default=1)
    parser.add_argument("--min-response-chars", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dolly_rows = iter_dolly(Path(args.dolly_path), args.dolly_limit, args.min_response_chars)
    openorca_rows = iter_openorca(Path(args.openorca_path), args.openorca_limit, args.min_response_chars)
    ultrachat_rows = iter_ultrachat(
        Path(args.ultrachat_path),
        args.ultrachat_limit,
        args.max_pairs_per_dialog,
        args.min_response_chars,
    )
    lang_set = {item.strip() for item in args.oasst_langs.split(",") if item.strip()}
    oasst_rows = iter_oasst(Path(args.oasst_path), args.oasst_limit, lang_set, args.min_response_chars)

    mixed = dolly_rows + openorca_rows + ultrachat_rows + oasst_rows
    # Reproducible shuffle for source balancing.
    import random

    random.Random(args.seed).shuffle(mixed)
    write_jsonl(Path(args.output), mixed)

    print(f"dolly: {len(dolly_rows)}")
    print(f"openorca: {len(openorca_rows)}")
    print(f"ultrachat: {len(ultrachat_rows)}")
    print(f"oasst1: {len(oasst_rows)}")
    print(f"total: {len(mixed)} -> {args.output}")


if __name__ == "__main__":
    main()
