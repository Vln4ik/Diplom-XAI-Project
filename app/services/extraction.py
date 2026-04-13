from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.preprocessing import make_excerpt, normalize_text, read_document_text


SOURCE_QUALITY_BY_EXT = {
    ".csv": 0.95,
    ".json": 0.95,
    ".xlsx": 0.9,
    ".xlsm": 0.9,
    ".txt": 0.85,
    ".md": 0.85,
    ".docx": 0.8,
    ".pdf": 0.75,
}


def _normalize_value(value: str, value_type: str) -> str | int | None:
    cleaned = normalize_text(value)
    if value_type == "number":
        digits = re.sub(r"[^\d]", "", cleaned)
        return int(digits) if digits else None
    return cleaned or None


def _source_quality(path: Path) -> float:
    return SOURCE_QUALITY_BY_EXT.get(path.suffix.lower(), 0.65)


def load_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for doc in documents:
        path = Path(doc["stored_path"])
        text = read_document_text(path)
        loaded.append(
            {
                "document_id": doc["id"],
                "file_name": doc["file_name"],
                "stored_path": str(path),
                "content": text,
                "quality": _source_quality(path),
            }
        )
    return loaded


def extract_facts(profile: dict[str, Any], documents: list[dict[str, Any]]) -> dict[str, Any]:
    loaded_docs = load_documents(documents)
    facts: list[dict[str, Any]] = []

    required_total = 0
    required_filled = 0

    for field_id, field_def in profile["fields"].items():
        required = bool(field_def.get("required"))
        if required:
            required_total += 1

        candidates: list[dict[str, Any]] = []
        for doc in loaded_docs:
            text = doc["content"]
            if not text:
                continue
            for pattern in field_def["patterns"]:
                regex_pattern = pattern.replace("\\\\", "\\")
                for match in re.finditer(regex_pattern, text, re.IGNORECASE | re.MULTILINE):
                    raw_value = match.group(1) if match.lastindex else match.group(0)
                    normalized_value = _normalize_value(raw_value, field_def["type"])
                    if field_def["type"] == "text" and (normalized_value is None or len(str(normalized_value)) < 2):
                        continue
                    if field_def["type"] == "number" and normalized_value is None:
                        continue
                    candidates.append(
                        {
                            "value": normalized_value,
                            "source_file": doc["file_name"],
                            "source_excerpt": make_excerpt(text, match.start(), match.end()),
                            "source_quality": doc["quality"],
                        }
                    )

        if not candidates:
            facts.append(
                {
                    "field": field_id,
                    "label": field_def["label"],
                    "value": None,
                    "value_type": field_def["type"],
                    "required": required,
                    "confidence": 0.0,
                    "source_score": 0.0,
                    "has_conflict": False,
                    "all_detected_values": [],
                    "sources": [],
                }
            )
            continue

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            grouped[str(candidate["value"])].append(candidate)

        chosen_value, chosen_candidates = max(grouped.items(), key=lambda item: len(item[1]))
        has_conflict = len(grouped) > 1
        source_count = len({item["source_file"] for item in chosen_candidates})
        source_score = sum(item["source_quality"] for item in chosen_candidates) / len(chosen_candidates)
        consistency_score = 1.0 if not has_conflict else 0.65

        confidence = min(0.99, 0.5 + 0.18 * source_score + 0.12 * min(source_count, 3) + 0.2 * consistency_score)

        if field_def["type"] == "number":
            typed_value: str | int = int(chosen_value)
        else:
            typed_value = chosen_value

        if required and typed_value not in (None, ""):
            required_filled += 1

        facts.append(
            {
                "field": field_id,
                "label": field_def["label"],
                "value": typed_value,
                "value_type": field_def["type"],
                "required": required,
                "confidence": round(confidence, 3),
                "source_score": round(source_score, 3),
                "has_conflict": has_conflict,
                "all_detected_values": list(grouped.keys()),
                "sources": [
                    {
                        "source_file": item["source_file"],
                        "source_excerpt": item["source_excerpt"],
                    }
                    for item in chosen_candidates[:3]
                ],
            }
        )

    score_complete = (required_filled / required_total) if required_total else 1.0

    return {
        "facts": facts,
        "score_complete": round(score_complete, 3),
        "required_filled": required_filled,
        "required_total": required_total,
    }
