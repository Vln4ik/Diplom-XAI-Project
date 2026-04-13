from __future__ import annotations

from typing import Any
from uuid import uuid4


def build_norm_references(profile: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for fact in facts:
        field = fact["field"]
        field_def = profile["fields"][field]
        for norm in field_def.get("norm_references", []):
            references.append(
                {
                    "id": f"norm-{uuid4().hex[:10]}",
                    "field": field,
                    "fact_value": fact["value"],
                    "norm_code": norm["code"],
                    "document": norm["document"],
                    "clause": norm["clause"],
                    "level": norm.get("level", "mandatory"),
                    "is_active": bool(fact["value"]),
                }
            )
    return references
