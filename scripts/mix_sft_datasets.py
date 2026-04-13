from __future__ import annotations

import argparse
import json
import random
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


def parse_input_spec(spec: str) -> tuple[Path, int]:
    if ":" in spec:
        file_path, limit = spec.rsplit(":", 1)
        return Path(file_path), int(limit)
    return Path(spec), 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Mix multiple SFT jsonl datasets with optional per-file limits")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="Path or path:limit, e.g. data/a.jsonl:5000",
    )
    parser.add_argument("--output", default="data/processed/sft_mixed.jsonl")
    parser.add_argument("--max-total", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    rows: list[dict] = []
    for spec in args.input:
        path, limit = parse_input_spec(spec)
        part = load_jsonl(path)
        if limit > 0:
            part = part[:limit]
        rows.extend(part)
        print(f"Loaded {len(part)} rows from {path}")

    random.shuffle(rows)

    deduped: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        key = row.get("text", "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if args.max_total > 0:
        deduped = deduped[: args.max_total]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in deduped:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(deduped)} rows -> {out_path}")


if __name__ == "__main__":
    main()
