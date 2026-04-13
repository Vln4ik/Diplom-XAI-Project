from __future__ import annotations

import re
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from app.services.llm import rewrite_sections_with_llm

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def _calc_score_conf(s_source: float, s_consistency: float, s_norm: float) -> float:
    return round(0.4 * s_source + 0.35 * s_consistency + 0.25 * s_norm, 3)


def _render_template(template: str, facts_by_field: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    missing_fields: list[str] = []

    def replacement(match: re.Match[str]) -> str:
        field = match.group(1)
        fact = facts_by_field.get(field)
        if not fact or fact["value"] in (None, ""):
            missing_fields.append(field)
            return "ОТСУТСТВУЕТ"
        return str(fact["value"])

    rendered = PLACEHOLDER_RE.sub(replacement, template)
    return rendered, missing_fields


def _section_metrics(
    section_fields: list[str],
    facts_by_field: dict[str, dict[str, Any]],
    norm_refs_by_field: dict[str, list[dict[str, Any]]],
) -> tuple[float, float, float, float]:
    relevant_facts = [facts_by_field.get(field) for field in section_fields]
    present_facts = [fact for fact in relevant_facts if fact and fact["value"] not in (None, "")]

    if present_facts:
        s_source = mean(fact["confidence"] for fact in present_facts)
        conflict_count = sum(1 for fact in present_facts if fact.get("has_conflict"))
        s_consistency = max(0.3, 1 - (conflict_count / len(present_facts)) * 0.5)
    else:
        s_source = 0.0
        s_consistency = 0.3

    required_fields = [field for field in section_fields if facts_by_field.get(field, {}).get("required")]
    required_filled = [field for field in required_fields if facts_by_field[field]["value"] not in (None, "")]
    score_complete = (len(required_filled) / len(required_fields)) if required_fields else 1.0

    if required_fields:
        norm_covered = sum(1 for field in required_fields if norm_refs_by_field.get(field))
        s_norm = norm_covered / len(required_fields)
    else:
        s_norm = 1.0

    score_conf = _calc_score_conf(s_source, s_consistency, s_norm)
    return round(s_source, 3), round(s_consistency, 3), round(score_complete, 3), score_conf


def generate_report(
    profile: dict[str, Any],
    facts: list[dict[str, Any]],
    norm_references: list[dict[str, Any]],
    conf_threshold: float = 0.75,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    facts_by_field = {fact["field"]: fact for fact in facts}

    norm_refs_by_field: dict[str, list[dict[str, Any]]] = {}
    for reference in norm_references:
        norm_refs_by_field.setdefault(reference["field"], []).append(reference)

    sections: list[dict[str, Any]] = []
    evidence_map: list[dict[str, Any]] = []
    section_facts_by_id: dict[str, list[dict[str, Any]]] = {}

    for section in profile["sections"]:
        rendered_text, missing_fields = _render_template(section["template"], facts_by_field)
        s_source, s_consistency, score_complete, score_conf = _section_metrics(
            section["fields"], facts_by_field, norm_refs_by_field
        )

        status = "requires_review" if score_conf < conf_threshold or score_complete < 1.0 else "ready"

        section_record = {
            "section_id": section["id"],
            "title": section["title"],
            "text": rendered_text,
            "missing_fields": missing_fields,
            "metrics": {
                "S_source": s_source,
                "S_consistency": s_consistency,
                "Score_complete": score_complete,
                "Score_conf": score_conf,
            },
            "status": status,
            "validation_status": "pending",
        }
        sections.append(section_record)

        links: list[dict[str, Any]] = []
        for field in section["fields"]:
            fact = facts_by_field.get(field)
            if not fact:
                continue
            links.append(
                {
                    "field": field,
                    "label": fact["label"],
                    "value": fact["value"],
                    "confidence": fact["confidence"],
                    "required": fact["required"],
                    "sources": fact["sources"],
                    "norm_references": norm_refs_by_field.get(field, []),
                }
            )
        section_facts_by_id[section["id"]] = links

        evidence_map.append(
            {
                "section_id": section["id"],
                "section_title": section["title"],
                "status": status,
                "score_conf": score_conf,
                "score_complete": score_complete,
                "links": links,
            }
        )

    llm_result = rewrite_sections_with_llm(sections, section_facts_by_id=section_facts_by_id, use_llm=use_llm)
    if llm_result["rewrites"]:
        for section in sections:
            section["text"] = llm_result["rewrites"].get(section["section_id"], section["text"])

    overall_score_conf = round(mean(section["metrics"]["Score_conf"] for section in sections), 3) if sections else 0.0

    required_facts = [fact for fact in facts if fact.get("required")]
    required_filled = [fact for fact in required_facts if fact["value"] not in (None, "")]
    overall_score_complete = round((len(required_filled) / len(required_facts)) if required_facts else 1.0, 3)

    raw_text = "\n\n".join(f"{section['title']}\n{section['text']}" for section in sections)

    draft = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_id": profile["id"],
        "generation_meta": {
            "llm_mode": llm_result["mode"],
            "llm_enabled": llm_result["enabled"],
            "llm_available": llm_result["available"],
            "llm_applied_sections": llm_result["applied_sections"],
            "llm_reason": llm_result["reason"],
            "llm_model": llm_result["model"],
            "llm_adapter": llm_result["adapter"],
        },
        "overall_metrics": {
            "Score_conf": overall_score_conf,
            "Score_complete": overall_score_complete,
        },
        "sections": sections,
        "raw_text": raw_text,
    }

    return {
        "draft": draft,
        "evidence_map": evidence_map,
    }
