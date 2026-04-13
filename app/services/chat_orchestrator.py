from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.chat_models import generate_model_analysis, model_uses_lora_rewriter, resolve_model_id
from app.services.extraction import extract_facts
from app.services.generation import generate_report
from app.services.normative import build_norm_references
from app.services.preprocessing import EXCEL_EXTENSIONS, TEXT_EXTENSIONS, read_document_text
from app.services.profiles import get_profile
from app.storage import add_audit, add_document, create_report, get_report, list_reports, save_report, upload_dir

_PROFILE_HINTS = {
    "rospotrebnadzor": ("роспотреб", "rpn", "rospotreb"),
    "rosobrnadzor": ("рособр", "robr", "rosobrn"),
}

_MODEL_LABELS = {
    "pipeline-basic": "Pipeline Basic",
    "general-assistant": "General Assistant",
    "lora-rewriter": "LoRA Rewriter",
    "full-analyst": "Full Analyst",
}

_SUPPORTED_ANALYSIS_EXTENSIONS = set(TEXT_EXTENSIONS) | set(EXCEL_EXTENSIONS) | {".docx", ".pdf"}


@dataclass
class ChatAttachment:
    file_name: str
    content_type: str | None
    data: bytes


def _detect_profile_from_message(message: str, fallback: str) -> str:
    lower = message.lower()
    for profile_id, hints in _PROFILE_HINTS.items():
        if any(hint in lower for hint in hints):
            return profile_id
    return fallback


def _extract_title(message: str) -> str:
    quoted = re.search(r'["“«]([^"”»]{3,140})["”»]', message)
    if quoted:
        return quoted.group(1).strip()
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "Чатовый запуск отчета"
    return cleaned[:120]


def _plan_actions(message: str, has_files: bool, has_report: bool) -> list[str]:
    lower = message.lower()
    if has_files and not lower.strip():
        actions: list[str] = []
        if not has_report:
            actions.append("create")
        actions.extend(["upload", "extract", "generate", "analyze"])
        return actions

    actions: list[str] = []

    full_pipeline = bool(re.search(r"полный пайплайн|сделай все|сделай всё|full pipeline|run all", lower))
    if full_pipeline:
        if not has_report:
            actions.append("create")
        if has_files:
            actions.append("upload")
        actions.extend(["extract", "generate", "analyze"])
        return actions

    if re.search(r"создай|новый отчет|новый отч[её]т|create|new report", lower):
        actions.append("create")
    if has_files or re.search(r"загрузи|прикреп|upload|attach", lower):
        actions.append("upload")
    if re.search(r"извлеки|extract|факты", lower):
        actions.append("extract")
    if re.search(r"сгенерируй|черновик|draft|generate", lower):
        actions.append("generate")
    if re.search(r"покажи черновик|покажи draft|get draft|текст отч", lower):
        actions.append("draft")
    if re.search(r"объясн|explain|доказат", lower):
        actions.append("explain")
    if re.search(r"статус|status|инфо", lower):
        actions.append("status")
    if re.search(r"список отч|list reports|reports list", lower):
        actions.append("list_reports")
    if re.search(r"анализ|проанализ|оцен|риски|improve|улучш|quality", lower):
        actions.append("analyze")

    if not actions:
        if has_files:
            if not has_report:
                actions.append("create")
            actions.extend(["upload", "extract", "generate", "analyze"])
        elif has_report:
            actions.append("analyze")
        else:
            actions.append("help")

    seen: set[str] = set()
    ordered: list[str] = []
    for action in actions:
        if action in seen:
            continue
        seen.add(action)
        ordered.append(action)
    return ordered


def _report_context(report: dict[str, Any]) -> str:
    draft = report.get("report_draft") or {}
    metrics = draft.get("overall_metrics") or {}
    sections = draft.get("sections") or []
    raw_text = draft.get("raw_text") or ""
    lines = [
        f"report_id={report.get('id')}",
        f"profile_id={report.get('profile_id')}",
        f"status={report.get('status')}",
        f"Score_conf={metrics.get('Score_conf', 'n/a')}",
        f"Score_complete={metrics.get('Score_complete', 'n/a')}",
        f"sections={len(sections)}",
        "",
        "RAW_TEXT:",
        raw_text or "Черновик пока не сгенерирован.",
    ]
    return "\n".join(lines)


def _documents_context(report: dict[str, Any], max_chars: int = 5200) -> str:
    parts: list[str] = []
    used = 0
    for doc in report.get("documents", []):
        path = Path(doc.get("stored_path", ""))
        if not path.exists():
            continue
        text = read_document_text(path).strip()
        if not text:
            continue
        chunk = f"[Файл: {doc.get('file_name', path.name)}]\n{text}"
        if used + len(chunk) > max_chars:
            remaining = max_chars - used
            if remaining <= 120:
                break
            chunk = chunk[:remaining] + "\n...[truncated]"
        parts.append(chunk)
        used += len(chunk)
        if used >= max_chars:
            break
    return "\n\n".join(parts)


def _ensure_report(
    current_report: dict[str, Any] | None,
    title_hint: str,
    profile_id: str,
) -> tuple[dict[str, Any], bool]:
    if current_report is not None:
        return current_report, False
    report = create_report(title=title_hint, profile_id=profile_id)
    return report, True


def _has_any_fact_values(facts: list[dict[str, Any]]) -> bool:
    for fact in facts:
        value = fact.get("value")
        if value not in (None, ""):
            return True
    return False


def _short_value(value: Any, max_len: int = 96) -> str:
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_compliance_summary(report: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    profile = get_profile(report["profile_id"])
    extracted = report.get("extracted_facts") or []
    facts_by_field = {item.get("field"): item for item in extracted}

    required_ids = [field_id for field_id, field_def in profile["fields"].items() if field_def.get("required")]
    required_total = len(required_ids)
    required_filled = 0

    field_checks: list[dict[str, Any]] = []
    missing_required_labels: list[str] = []

    for field_id in required_ids:
        field_def = profile["fields"][field_id]
        fact = facts_by_field.get(field_id, {})
        value = fact.get("value")
        is_present = value not in (None, "")
        if is_present:
            required_filled += 1
        else:
            missing_required_labels.append(field_def["label"])

        field_checks.append(
            {
                "field": field_id,
                "label": field_def["label"],
                "present": is_present,
                "value": None if not is_present else str(value),
                "confidence": fact.get("confidence", 0.0),
            }
        )

    draft = report.get("report_draft") or {}
    overall = draft.get("overall_metrics") or {}
    score_complete = overall.get("Score_complete")
    score_conf = overall.get("Score_conf")

    sections = draft.get("sections") or []
    requires_review_sections = [section.get("title", section.get("section_id", "unknown")) for section in sections if section.get("status") == "requires_review"]

    if required_total and required_filled == required_total and (score_conf is None or float(score_conf) >= 0.75):
        verdict = "Соответствует базовым обязательным требованиям профиля."
        verdict_code = "pass"
    elif required_filled == 0:
        verdict = "Не соответствует: обязательные реквизиты не извлечены."
        verdict_code = "fail"
    else:
        verdict = "Частичное соответствие: часть обязательных реквизитов отсутствует или требует ручной проверки."
        verdict_code = "partial"

    lines: list[str] = [
        f"Проверка соответствия профилю: {profile['title']}",
        f"Итог: {verdict}",
        (
            f"Обязательные поля: {required_filled}/{required_total}. "
            f"Score_complete={score_complete if score_complete is not None else 'n/a'}, "
            f"Score_conf={score_conf if score_conf is not None else 'n/a'}."
        ),
        "",
        "Статус обязательных полей:",
    ]
    for item in field_checks:
        status = "заполнено" if item["present"] else "не заполнено"
        value = _short_value(item["value"]) if item["present"] else "ОТСУТСТВУЕТ"
        lines.append(f"- {item['label']}: {status}; значение: {value}.")

    if missing_required_labels or requires_review_sections:
        lines.append("")
        lines.append("Что нужно доработать:")
        if missing_required_labels:
            lines.append("- Заполнить обязательные поля: " + ", ".join(missing_required_labels) + ".")
        if requires_review_sections:
            lines.append("- Проверить разделы со статусом requires_review: " + ", ".join(requires_review_sections) + ".")

    payload = {
        "verdict": verdict_code,
        "verdict_text": verdict,
        "required_filled": required_filled,
        "required_total": required_total,
        "missing_required_fields": missing_required_labels,
        "review_sections": requires_review_sections,
        "score_complete": score_complete,
        "score_conf": score_conf,
        "fields": field_checks,
    }
    return "\n".join(lines), payload


def _is_compliance_request(message: str) -> bool:
    lower = message.lower()
    return bool(re.search(r"соответств|проверк|надзор|комплаенс|compliance|валид", lower))


def _build_assistant_explanation(
    selected_model: str,
    actions: list[str],
    payload: dict[str, Any],
    report: dict[str, Any] | None,
    files_count: int,
) -> str:
    lines: list[str] = []
    model_label = _MODEL_LABELS.get(selected_model, selected_model)
    lines.append(f"Модель ответа: {model_label}.")

    if actions:
        lines.append(f"Выполненные шаги: {', '.join(actions)}.")

    if files_count:
        lines.append(f"Принято файлов в этом запросе: {files_count}.")

    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        reason = str(analysis.get("reason", "")).strip()
        if reason == "deterministic_compliance":
            lines.append("Ответ сформирован детерминированной проверкой соответствия профилю.")
        elif analysis.get("applied"):
            lines.append("Ответ сгенерирован языковой моделью по запросу и доступному контексту.")
        else:
            lines.append("Ответ выдан в fallback/эвристическом режиме.")
        if reason and reason not in {"ok", "heuristic_mode", "deterministic_compliance"}:
            lines.append(f"Техническая причина fallback: {reason}.")

    extract = payload.get("extract")
    if isinstance(extract, dict):
        lines.append(
            "Извлечение фактов: "
            f"{extract.get('required_filled', 'n/a')}/{extract.get('required_total', 'n/a')} "
            f"(Score_complete={extract.get('score_complete', 'n/a')})."
        )

    generate = payload.get("generate")
    if isinstance(generate, dict):
        overall = generate.get("overall_metrics", {})
        meta = generate.get("generation_meta", {})
        lines.append(
            "Генерация отчета: "
            f"Score_conf={overall.get('Score_conf', 'n/a')}, "
            f"Score_complete={overall.get('Score_complete', 'n/a')}, "
            f"llm_mode={meta.get('llm_mode', 'n/a')}."
        )

    if report is not None:
        lines.append(f"Контекст: report_id={report.get('id', '-')}, status={report.get('status', '-')}.")

    return "\n".join(lines)


def process_chat_turn(
    message: str,
    profile_id: str,
    model_id: str,
    report_id: str | None = None,
    attachments: list[ChatAttachment] | None = None,
) -> dict[str, Any]:
    normalized_message = (message or "").strip()
    selected_model = resolve_model_id(model_id)
    files = attachments or []

    report = get_report(report_id) if report_id else None
    effective_profile_id = _detect_profile_from_message(normalized_message, profile_id)

    if report is not None and report.get("profile_id") != effective_profile_id:
        effective_profile_id = report["profile_id"]
    else:
        get_profile(effective_profile_id)

    actions = _plan_actions(normalized_message, has_files=bool(files), has_report=report is not None)
    if selected_model == "general-assistant" and actions == ["help"] and normalized_message:
        actions = ["chat"]

    response_lines: list[str] = []
    payload: dict[str, Any] = {"actions": actions}
    dirty = False

    for action in actions:
        if action == "chat":
            context = _report_context(report) if report is not None else ""
            analysis = generate_model_analysis(selected_model, normalized_message, context)
            response_lines.append(analysis["text"])
            payload["analysis"] = {
                "model_id": analysis["model_id"],
                "applied": analysis["applied"],
                "reason": analysis["reason"],
            }
            continue

        if action == "help":
            response_lines.append(
                "Напишите действие: создать отчет, загрузить файлы, извлечь факты, сгенерировать черновик, показать explain или проанализировать отчет."
            )
            continue

        if action == "create":
            if report is None:
                report, created = _ensure_report(report, _extract_title(normalized_message), effective_profile_id)
            else:
                report = create_report(title=_extract_title(normalized_message), profile_id=effective_profile_id)
                created = True
            dirty = dirty or created
            response_lines.append(f"Создан отчет: {report['id']}")
            continue

        if action == "list_reports":
            items = list_reports()
            if not items:
                response_lines.append("Отчетов пока нет.")
            else:
                rows = [f"{idx + 1}. {item['id']} | {item['profile_id']} | {item['status']}" for idx, item in enumerate(items[:10])]
                response_lines.append("Последние отчеты:\n" + "\n".join(rows))
            continue

        if action == "upload":
            report, created = _ensure_report(report, _extract_title(normalized_message), effective_profile_id)
            dirty = dirty or created
            if not files:
                response_lines.append("Файлы не приложены.")
                continue

            target_dir = upload_dir(report["id"])
            uploaded_count = 0
            unsupported: list[str] = []
            for file in files:
                if not file.data:
                    continue
                safe_name = Path(file.file_name or "document.bin").name
                if Path(safe_name).suffix.lower() not in _SUPPORTED_ANALYSIS_EXTENSIONS:
                    unsupported.append(safe_name)
                stored_name = f"{uuid4().hex[:8]}_{safe_name}"
                stored_path = target_dir / stored_name
                stored_path.write_bytes(file.data)
                add_document(
                    report,
                    file_name=safe_name,
                    stored_path=str(stored_path),
                    mime_type=file.content_type,
                    size_bytes=len(file.data),
                )
                uploaded_count += 1
            report["status"] = "documents_uploaded"
            dirty = True
            response_lines.append(f"Загружено файлов: {uploaded_count}")
            if unsupported:
                response_lines.append(
                    "Предупреждение: часть файлов пока не поддерживает автоматическое извлечение текста: "
                    + ", ".join(unsupported)
                )
            payload["uploaded_files"] = uploaded_count
            if unsupported:
                payload["unsupported_files"] = unsupported
            continue

        if action == "extract":
            report, created = _ensure_report(report, _extract_title(normalized_message), effective_profile_id)
            dirty = dirty or created
            if not report["documents"]:
                response_lines.append("Нет документов для извлечения. Сначала загрузите файлы.")
                continue
            profile = get_profile(report["profile_id"])
            extracted = extract_facts(profile=profile, documents=report["documents"])
            report["extracted_facts"] = extracted["facts"]
            report["status"] = "facts_extracted"
            add_audit(
                report,
                "facts_extracted",
                {
                    "required_filled": extracted["required_filled"],
                    "required_total": extracted["required_total"],
                    "score_complete": extracted["score_complete"],
                },
            )
            dirty = True
            response_lines.append(
                f"Факты извлечены: обязательные поля {extracted['required_filled']}/{extracted['required_total']} (Score_complete={extracted['score_complete']})."
            )
            payload["extract"] = {
                "required_filled": extracted["required_filled"],
                "required_total": extracted["required_total"],
                "score_complete": extracted["score_complete"],
            }
            continue

        if action == "generate":
            report, created = _ensure_report(report, _extract_title(normalized_message), effective_profile_id)
            dirty = dirty or created
            if not report["extracted_facts"]:
                response_lines.append("Сначала выполните извлечение фактов.")
                continue
            if not _has_any_fact_values(report["extracted_facts"]):
                response_lines.append(
                    "Не удалось извлечь содержательные данные из файлов, поэтому генерация черновика пропущена."
                )
                if payload.get("unsupported_files"):
                    response_lines.append(
                        "Загрузите поддерживаемый текстовый формат или конвертируйте файл: "
                        ".txt, .md, .csv, .json, .log, .docx, .pdf, .xlsx."
                    )
                payload["generate"] = {
                    "skipped": True,
                    "reason": "no_extracted_values",
                }
                continue

            profile = get_profile(report["profile_id"])
            norm_refs = build_norm_references(profile, report["extracted_facts"])
            generated = generate_report(
                profile=profile,
                facts=report["extracted_facts"],
                norm_references=norm_refs,
                use_llm=model_uses_lora_rewriter(selected_model),
            )
            report["norm_references"] = norm_refs
            report["report_draft"] = generated["draft"]
            report["evidence_map"] = generated["evidence_map"]
            report["status"] = "draft_generated"
            add_audit(
                report,
                "report_generated",
                {
                    "score_conf": generated["draft"]["overall_metrics"]["Score_conf"],
                    "score_complete": generated["draft"]["overall_metrics"]["Score_complete"],
                    "llm_mode": generated["draft"]["generation_meta"]["llm_mode"],
                },
            )
            dirty = True
            meta = generated["draft"]["generation_meta"]
            response_lines.append(
                f"Черновик сформирован. Score_conf={generated['draft']['overall_metrics']['Score_conf']}, "
                f"Score_complete={generated['draft']['overall_metrics']['Score_complete']}, llm_mode={meta['llm_mode']}."
            )
            payload["generate"] = {
                "overall_metrics": generated["draft"]["overall_metrics"],
                "generation_meta": meta,
            }
            continue

        if action == "draft":
            if report is None or not report.get("report_draft"):
                response_lines.append("Черновик пока не сгенерирован.")
                continue
            raw_text = report["report_draft"].get("raw_text", "")
            preview = raw_text[:2800]
            response_lines.append("Черновик отчета:\n" + preview)
            payload["draft_preview_len"] = len(preview)
            continue

        if action == "explain":
            if report is None or not report.get("evidence_map"):
                response_lines.append("Карта доказательств отсутствует. Запустите генерацию.")
                continue
            response_lines.append(f"Карта доказательств доступна. Разделов: {len(report['evidence_map'])}.")
            payload["evidence_sections"] = len(report["evidence_map"])
            continue

        if action == "status":
            if report is None:
                response_lines.append("Текущий чат еще не связан с отчетом.")
                continue
            response_lines.append(
                f"Статус: {report['status']}. Документов: {len(report['documents'])}. Фактов: {len(report['extracted_facts'])}."
            )
            continue

        if action == "analyze":
            if report is None:
                if selected_model == "general-assistant":
                    analysis = generate_model_analysis(selected_model, normalized_message, "")
                    response_lines.append(analysis["text"])
                    payload["analysis"] = {
                        "model_id": analysis["model_id"],
                        "applied": analysis["applied"],
                        "reason": analysis["reason"],
                    }
                    continue
                response_lines.append("Нет отчета для анализа. Создайте отчет и загрузите данные.")
                continue
            if not report.get("report_draft"):
                doc_context = _documents_context(report)
                if doc_context:
                    analyze_query = normalized_message or "Сделай краткий анализ содержимого загруженных файлов."
                    analysis = generate_model_analysis(selected_model, analyze_query, doc_context)
                    response_lines.append(analysis["text"])
                    payload["analysis"] = {
                        "model_id": analysis["model_id"],
                        "applied": analysis["applied"],
                        "reason": analysis["reason"],
                    }
                    continue
                response_lines.append(
                    "Анализ пропущен: в черновике и документах нет извлеченного текста для анализа."
                )
                payload["analysis"] = {
                    "model_id": selected_model,
                    "applied": False,
                    "reason": "no_draft",
                }
                continue
            if not normalized_message or _is_compliance_request(normalized_message):
                compliance_text, compliance_payload = _build_compliance_summary(report)
                response_lines.append(compliance_text)
                payload["analysis"] = {
                    "model_id": selected_model,
                    "applied": False,
                    "reason": "deterministic_compliance",
                }
                payload["compliance"] = compliance_payload
                continue
            context = _report_context(report)
            analysis = generate_model_analysis(selected_model, normalized_message, context)
            response_lines.append(analysis["text"])
            payload["analysis"] = {
                "model_id": analysis["model_id"],
                "applied": analysis["applied"],
                "reason": analysis["reason"],
            }
            continue

    if report is not None and dirty:
        save_report(report)

    if not response_lines:
        response_lines.append("Команда принята, но действий не выполнено. Уточните запрос.")

    explanation = _build_assistant_explanation(
        selected_model=selected_model,
        actions=actions,
        payload=payload,
        report=report,
        files_count=len(files),
    )
    payload["assistant_explanation"] = explanation

    return {
        "report_id": report["id"] if report else report_id or "",
        "profile_id": report["profile_id"] if report else effective_profile_id,
        "model_id": selected_model,
        "actions": actions,
        "reply": "\n\n".join(response_lines),
        "explanation": explanation,
        "data": payload,
    }
