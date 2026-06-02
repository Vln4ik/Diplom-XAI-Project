from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.llm.local import get_llm_provider
from app.models import (
    Document,
    DocumentStatus,
    ExpertiseFinding,
    ExpertiseUserDecision,
    ExpertiseWorkflow,
    ExpertiseWorkflowStage,
    Report,
    ReportStatus,
)
from app.services.audit import log_action
from app.services.report_types import STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT
from app.services.terminology_quality import TerminologyIssue, assess_terminology_quality
from app.services.visual_quality import VisualQualityAssessment, assess_visual_quality
from app.services.visual_signatures import VisualSignatureDetection, detect_visual_signature_or_seal

MODEL_VERSION = "estimate-expertise-local-terminology-baseline-v7"
RULE_VERSION = "estimate-cost-pp145-rules-pack-v8"
PP87_RULE_VERSION = "estimate-cost-pp87-rules-pack-v3"
OPEN_STATUSES = {"open", "replacement_processing"}
PIPELINE_ACTIVE_STATUSES = {"queued", "running"}
READY_DOCUMENT_STATUSES = {DocumentStatus.processed, DocumentStatus.requires_review}
SIGNATURE_MARKERS = ("подпись", "подписал", "подписано", "м.п", "м. п", "печать", "гип", "утверждаю", "директор")
VISUAL_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
IMAGE_DOCUMENT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
ANALYSIS_STAGE_KEYS = {"filename_content", "completeness", "section_content", "quality_spell_signature"}
REPORT_STATUS_LOCKED_BY_USER = {
    ReportStatus.awaiting_approval,
    ReportStatus.approved,
    ReportStatus.exported,
    ReportStatus.archived,
}


@dataclass(frozen=True)
class StageDefinition:
    key: str
    title: str
    short_title: str


@dataclass(frozen=True)
class RequiredDocumentGroup:
    key: str
    title: str
    patterns: tuple[str, ...]
    content_patterns: tuple[str, ...]
    normative_basis: str
    required_level: str = "mandatory"


@dataclass(frozen=True)
class EstimateRulesProfile:
    key: str
    regulation_label: str
    rule_version: str
    required_groups: tuple[RequiredDocumentGroup, ...]
    stage_definitions: tuple[StageDefinition, ...]


@dataclass(frozen=True)
class DocumentTypeEvidence:
    group: RequiredDocumentGroup
    score: float
    matched_terms: tuple[str, ...]
    snippets: tuple[str, ...]


@dataclass(frozen=True)
class DocumentTypeClassification:
    predicted_group: RequiredDocumentGroup | None
    confidence: float
    method: str
    name_evidence: DocumentTypeEvidence | None
    content_evidence: DocumentTypeEvidence | None
    llm_label: str | None = None
    llm_confidence: float | None = None
    llm_reason: str | None = None


STAGE_DEFINITIONS = (
    StageDefinition("start", "Запуск", "Запуск"),
    StageDefinition("filename_content", "Проверка соответствия содержания названию", "Название и содержание"),
    StageDefinition("completeness", "Проверка комплектности документов", "Комплектность"),
    StageDefinition("quality_spell_signature", "Лексическая, орфографическая и визуальная проверка", "Качество и подписи"),
    StageDefinition("final", "Финальная готовность", "Финал"),
)

PP87_STAGE_DEFINITIONS = (
    StageDefinition("start", "Запуск", "Запуск"),
    StageDefinition("filename_content", "Проверка соответствия содержания названию", "Название и содержание"),
    StageDefinition("section_content", "Проверка содержания разделов по ПП 87", "Содержание ПП 87"),
    StageDefinition("quality_spell_signature", "Лексическая, орфографическая и визуальная проверка", "Качество и подписи"),
    StageDefinition("final", "Финальная готовность", "Финал"),
)

PP145_REQUIRED_GROUPS = (
    RequiredDocumentGroup(
        "application",
        "Заявление о проведении государственной экспертизы",
        ("заявление", "заявка", "обращение"),
        ("заявление о проведении государственной экспертизы", "просим провести государственную экспертизу"),
        "ПП РФ N 145, пункт 13, подпункт `а`; форма заявления экспертной организации",
    ),
    RequiredDocumentGroup(
        "project_documentation",
        "Проектная документация на объект капитального строительства",
        ("проектная документация", "проект", "пд", "раздел"),
        ("проектная документация", "раздел проектной документации", "объект капитального строительства"),
        "ПП РФ N 145, пункт 13, подпункт `г`; состав и содержание проектной документации по законодательству РФ",
    ),
    RequiredDocumentGroup(
        "local_estimate",
        "Локальные сметные расчеты",
        ("лср", "локальн", "локальная смета", "локальный смет"),
        ("локальный сметный расчет", "локальная смета", "локальный смет", "локальн"),
        "ПП РФ N 145, проверка достоверности определения сметной стоимости; сметная документация",
    ),
    RequiredDocumentGroup(
        "object_estimate",
        "Объектные сметные расчеты",
        ("оср", "объектн", "объектная смета", "объектный смет"),
        ("объектный сметный расчет", "объектная смета", "объектн"),
        "ПП РФ N 145, проверка достоверности определения сметной стоимости; сметная документация",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "consolidated_estimate",
        "Сводный сметный расчет",
        ("сср", "сводн", "сводный смет"),
        ("сводный сметный расчет", "сводн", "итого по сводному"),
        "ПП РФ N 145, комплект сметной документации для проверки достоверности стоимости",
    ),
    RequiredDocumentGroup(
        "explanatory_note",
        "Пояснительная записка к сметной документации",
        ("поясн", "записка", "пз"),
        ("пояснительная записка", "пояснения к смет", "исходные данные"),
        "ПП РФ N 145 и внутренний профиль комплектности EvidenceXAI для сметной проверки",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "work_volume_statement",
        "Ведомости объемов работ, учтенных в сметных расчетах",
        ("вор", "ведомость объем", "ведомости объем", "объемы работ", "объём работ"),
        ("ведомость объемов работ", "ведомости объемов работ", "объемы работ", "объёмы работ"),
        "ПП РФ N 145, пункт 13, подпункт `г(1)`; ведомости объемов работ, учтенных в сметных расчетах",
    ),
    RequiredDocumentGroup(
        "price_justification",
        "Обоснования стоимости / коммерческие предложения",
        ("коммерч", "кп", "прайс", "обоснован", "стоимост"),
        ("коммерческое предложение", "прайс", "стоимость оборудования", "обоснование стоимости"),
        "ПП РФ N 145, проверка обоснованности расчета сметной стоимости; rules pack EvidenceXAI",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "design_assignment",
        "Задание на проектирование",
        ("задание на проектирование", "тз проект", "техническое задание", "зп"),
        ("задание на проектирование", "техническое задание на проектирование"),
        "ПП РФ N 145, пункт 13, подпункт `д`; задание на проектирование",
    ),
    RequiredDocumentGroup(
        "survey_results",
        "Результаты инженерных изысканий",
        ("инженерн изыск", "результаты изыск", "изыскания", "рии"),
        ("результаты инженерных изысканий", "инженерные изыскания", "отчет об инженерных изысканиях"),
        "ПП РФ N 145, пункт 13, подпункт `е`; результаты инженерных изысканий, если они требуются для объекта",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "survey_assignment",
        "Задание на выполнение инженерных изысканий",
        ("задание на изыск", "тз изыск", "задание инженерн"),
        ("задание на выполнение инженерных изысканий", "техническое задание на инженерные изыскания"),
        "ПП РФ N 145, пункт 13, подпункт `ж`; задание на выполнение инженерных изысканий, если изыскания представлены",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "applicant_authority",
        "Документы, подтверждающие полномочия заявителя",
        ("доверенность", "полномоч", "представитель", "действовать от имени"),
        ("документы подтверждающие полномочия", "доверенность", "действовать от имени"),
        "ПП РФ N 145, пункт 13, подпункт `и`; требуется, если заявитель действует от имени застройщика/технического заказчика",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "sro_extract_or_exemption",
        "Выписка СРО или документ об отсутствии обязанности членства",
        ("сро", "саморегулируем", "выписка из реестра", "членство"),
        ("выписка из реестра членов сро", "саморегулируемая организация", "членство в сро"),
        "ПП РФ N 145, пункт 13, подпункты `к` и `к(1)`; применяется при наличии обязанности членства в СРО",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "project_transfer_document",
        "Документ о передаче проектной документации заказчику",
        ("передача проект", "акт передачи", "передаточный акт", "передана застройщику"),
        ("документ подтверждающий передачу проектной документации", "акт передачи проектной документации"),
        "ПП РФ N 145, пункт 13, подпункт `к(2)`; документ о передаче проектной документации/изысканий",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "financing_decision",
        "Решение или акт о финансировании / подтверждении стоимости",
        ("финансирован", "предельная стоимость", "решение о финанс", "сметная стоимость", "источник финанс"),
        ("решение о финансировании", "акт о финансировании", "предельная стоимость", "источники финансирования"),
        "ПП РФ N 145, пункт 13, подпункты `л(1)` - `л(7)`; решения/акты о финансировании и подтверждении стоимости",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "individual_estimate_norms",
        "Сведения об индивидуальных сметных нормативах",
        ("индивидуальн сметн норматив", "исн", "решение правительства"),
        ("индивидуальные сметные нормативы", "решение правительства российской федерации"),
        "ПП РФ N 145, пункт 13, подпункт `л`; представляется, если принято решение о разработке и применении ИСН",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "historical_cultural_conclusion",
        "Положительное заключение государственной историко-культурной экспертизы",
        ("историко культур", "объект культурного наследия", "окн"),
        ("государственная историко-культурная экспертиза", "объект культурного наследия"),
        "ПП РФ N 145, пункт 13, подпункт `ж(1)`; требуется для объектов культурного наследия в установленных случаях",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "ecological_conclusion",
        "Положительное заключение государственной экологической экспертизы",
        ("экологическ экспертиз", "гээ", "росприроднадзор"),
        ("государственная экологическая экспертиза", "положительное заключение экологической экспертизы"),
        "ПП РФ N 145, пункт 13, подпункт `з`; требуется в случаях, предусмотренных экологическим законодательством",
        required_level="conditional",
    ),
)

PP87_REQUIRED_GROUPS = (
    RequiredDocumentGroup(
        "explanatory_note",
        "Пояснительная записка",
        ("пояснительная записка", "поясн", "пз"),
        ("пояснительная записка", "исходные данные", "технико экономические показатели"),
        "ПП РФ N 87, раздел 1; пояснительная записка в составе проектной документации",
    ),
    RequiredDocumentGroup(
        "land_plot_planning_scheme",
        "Схема планировочной организации земельного участка",
        ("спозу", "схема планировочной организации", "планировочн земельн"),
        ("схема планировочной организации земельного участка", "границы земельного участка", "планировочная организация"),
        "ПП РФ N 87, раздел 2; схема планировочной организации земельного участка",
    ),
    RequiredDocumentGroup(
        "architectural_solutions",
        "Объемно-планировочные и архитектурные решения",
        ("архитектурн", "ар", "архитектурные решения"),
        ("архитектурные решения", "фасад", "план этажа", "объемно пространственные решения"),
        "ПП РФ N 87, раздел 3; объемно-планировочные и архитектурные решения",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "structural_solutions",
        "Конструктивные решения",
        ("конструктивн", "кр", "конструктивные решения"),
        ("конструктивные решения", "несущие конструкции", "фундаменты", "каркас"),
        "ПП РФ N 87, раздел 4; конструктивные решения",
    ),
    RequiredDocumentGroup(
        "engineering_equipment_networks",
        "Сведения об инженерном оборудовании и сетях",
        ("иос", "инженерн оборуд", "инженерные сети", "водоснабж", "электроснабж", "отопление"),
        ("инженерное оборудование", "сети инженерно технического обеспечения", "водоснабжение", "электроснабжение"),
        "ПП РФ N 87, раздел 5; сведения об инженерном оборудовании, сетях и технических решениях",
    ),
    RequiredDocumentGroup(
        "technological_solutions",
        "Технологические решения",
        ("технологическ", "тр", "технологические решения"),
        ("технологические решения", "технологический процесс", "технологическое оборудование"),
        "ПП РФ N 87, раздел 6; технологические решения, если их разработка требуется заданием на проектирование",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "construction_organization_project",
        "Проект организации строительства",
        ("пос", "проект организации строительства", "организация строительства"),
        ("проект организации строительства", "календарный план строительства", "строительная площадка"),
        "ПП РФ N 87, раздел 7; проект организации строительства",
    ),
    RequiredDocumentGroup(
        "demolition_organization_project",
        "Проект организации работ по сносу или демонтажу",
        ("пор", "снос", "демонтаж", "проект организации работ"),
        ("проект организации работ по сносу", "демонтаж", "ликвидация объекта"),
        "ПП РФ N 87, раздел 7; проект организации работ по сносу включается в составе ПОС при необходимости сноса",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "environmental_protection",
        "Перечень мероприятий по охране окружающей среды",
        ("оос", "охрана окружающей среды", "экологическ"),
        ("мероприятия по охране окружающей среды", "воздействие на окружающую среду", "экологические мероприятия"),
        "ПП РФ N 87, раздел 8; мероприятия по охране окружающей среды",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "fire_safety",
        "Мероприятия по обеспечению пожарной безопасности",
        ("пб", "пожарн", "пожарная безопасность"),
        ("пожарная безопасность", "мероприятия по обеспечению пожарной безопасности", "эвакуация"),
        "ПП РФ N 87, раздел 9; мероприятия по обеспечению пожарной безопасности",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "safe_operation",
        "Требования к обеспечению безопасной эксплуатации",
        ("безопасн эксплуатац", "требования безопасной эксплуатации", "эксплуатац"),
        ("безопасная эксплуатация", "требования к обеспечению безопасной эксплуатации", "эксплуатационные требования"),
        "ПП РФ N 87, раздел 10; требования к обеспечению безопасной эксплуатации объектов капитального строительства",
        required_level="recommended",
    ),
    RequiredDocumentGroup(
        "accessibility_disabled",
        "Мероприятия по обеспечению доступа инвалидов",
        ("одс", "доступ инвалид", "маломобильн", "мгн"),
        ("доступ инвалидов", "маломобильные группы населения", "доступность объекта"),
        "ПП РФ N 87, раздел 11; мероприятия по обеспечению доступа инвалидов",
        required_level="conditional",
    ),
    RequiredDocumentGroup(
        "construction_estimate",
        "Смета на строительство, реконструкцию или капитальный ремонт",
        ("смета", "сметн", "сср", "лср", "локальный смет", "сводный смет"),
        ("смета на строительство", "сводный сметный расчет", "локальный сметный расчет", "сметная стоимость"),
        "ПП РФ N 87, раздел 12; смета на строительство, реконструкцию, капитальный ремонт или снос в случаях, указанных в пункте 3(4)",
    ),
    RequiredDocumentGroup(
        "other_required_documentation",
        "Иная документация в случаях, предусмотренных законодательством",
        ("иная документация", "специальн техническ", "сту", "дополнительн материал"),
        ("иная документация", "специальные технические условия", "требования законодательства"),
        "ПП РФ N 87, раздел 13; иная документация в случаях, предусмотренных законодательством и нормативными правовыми актами РФ",
        required_level="conditional",
    ),
)

PP145_RULES_PROFILE = EstimateRulesProfile(
    key="pp145",
    regulation_label="ПП РФ N 145",
    rule_version=RULE_VERSION,
    required_groups=PP145_REQUIRED_GROUPS,
    stage_definitions=STAGE_DEFINITIONS,
)

PP87_RULES_PROFILE = EstimateRulesProfile(
    key="pp87",
    regulation_label="ПП РФ N 87",
    rule_version=PP87_RULE_VERSION,
    required_groups=PP87_REQUIRED_GROUPS,
    stage_definitions=PP87_STAGE_DEFINITIONS,
)

REQUIRED_GROUPS = PP145_REQUIRED_GROUPS


def _rules_profile_for_report_type(report_type: str) -> EstimateRulesProfile:
    if report_type == STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT:
        return PP87_RULES_PROFILE
    return PP145_RULES_PROFILE


def _rules_profile_for_report(report: Report) -> EstimateRulesProfile:
    return _rules_profile_for_report_type(report.report_type)


def _rules_profile_for_workflow(workflow: ExpertiseWorkflow) -> EstimateRulesProfile:
    profile_key = str((workflow.state_json or {}).get("rules_profile") or "")
    if profile_key == PP87_RULES_PROFILE.key:
        return PP87_RULES_PROFILE
    return PP145_RULES_PROFILE


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def _stage_definition(stage_key: str, *, profile: EstimateRulesProfile = PP145_RULES_PROFILE) -> StageDefinition:
    return next(definition for definition in profile.stage_definitions if definition.key == stage_key)


def _load_workflow_documents(db: Session, report: Report) -> list[Document]:
    documents_query = select(Document).where(
        Document.organization_id == report.organization_id,
        Document.status.in_(READY_DOCUMENT_STATUSES),
    )
    if report.selected_document_ids:
        documents_query = documents_query.where(Document.id.in_(report.selected_document_ids))
    documents = list(db.scalars(documents_query))
    return sorted(documents, key=lambda item: (item.relative_path or item.file_name, item.file_name))


def _document_has_any_pattern(document: Document, patterns: tuple[str, ...]) -> bool:
    haystack = _normalize(
        f"{document.relative_path or ''} {document.file_name} {document.original_file_name or ''} {document.extracted_text or ''}"
    )
    return any(_normalize(pattern) in haystack for pattern in patterns)


def _has_required_group(documents: list[Document], patterns: tuple[str, ...]) -> bool:
    return any(_document_has_any_pattern(document, patterns) for document in documents)


def _document_content_text(document: Document) -> str:
    return _normalize(document.extracted_text or "")


def _document_extension(document: Document) -> str:
    candidate = document.relative_path or document.file_name or document.original_file_name or ""
    if "." not in candidate:
        return ""
    return f".{candidate.rsplit('.', 1)[-1].lower()}"


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]{2,}", text))


def _text_density_per_page(document: Document, content: str) -> float:
    return _word_count(content) / max(1, document.page_count or 1)


def _is_visual_document(document: Document) -> bool:
    extension = _document_extension(document)
    return extension in VISUAL_DOCUMENT_EXTENSIONS or "pdf" in (document.file_type or "").lower() or "image" in (document.file_type or "").lower()


def _is_image_document(document: Document) -> bool:
    extension = _document_extension(document)
    return extension in IMAGE_DOCUMENT_EXTENSIONS or "image" in (document.file_type or "").lower()


def _visual_detection_steps(detection: VisualSignatureDetection) -> list[str]:
    if not detection.available:
        return [f"Layout-aware detector недоступен: {detection.reason}."]
    if not detection.marks:
        return [detection.reason or "Layout-aware detector не нашел визуальных признаков подписи или печати."]
    steps = [
        f"Layout-aware detector: {detection.provider}, page={detection.page_number}, confidence={detection.confidence:.0%}.",
        f"Signature-like: {detection.signature_like}; seal-like: {detection.seal_like}.",
    ]
    for mark in detection.marks:
        steps.append(f"{mark.kind}: confidence={mark.confidence:.0%}, bbox={mark.bbox}, evidence={mark.evidence}.")
    return steps


def _visual_quality_steps(assessment: VisualQualityAssessment) -> list[str]:
    if not assessment.available:
        return [f"Visual quality detector недоступен: {assessment.reason}."]
    steps = [
        f"Visual quality detector: {assessment.provider}, page={assessment.page_number or 1}, confidence={assessment.confidence:.0%}.",
        f"Quality score: {assessment.quality_score:.0%}; contrast={assessment.contrast_score:.0%}; sharpness={assessment.sharpness_score:.0%}.",
        f"Dark ratio: {assessment.dark_ratio:.2%}; bright ratio: {assessment.bright_ratio:.2%}.",
    ]
    if assessment.issue_keys:
        steps.append(f"Найденные visual quality issues: {', '.join(_visual_quality_issue_label(key) for key in assessment.issue_keys)}.")
    else:
        steps.append("Visual quality detector не нашел критичных признаков плохого скана.")
    steps.extend(f"Evidence: {item}." for item in assessment.evidence)
    return steps


def _visual_quality_issue_label(issue_key: str) -> str:
    labels = {
        "low_resolution": "низкое разрешение",
        "low_contrast": "низкий контраст",
        "low_detail_or_blur": "мало деталей или возможная размытость",
        "blank_like": "страница похожа на пустую",
        "too_dark": "страница слишком темная",
        "mostly_empty": "почти пустая страница",
    }
    return labels.get(issue_key, issue_key)


def _terminology_issue_steps(issues: list[TerminologyIssue]) -> list[str]:
    steps = [
        "Проверка выполнена локальным rules-based словарем EvidenceXAI без внешних grammar/OCR API.",
        "Словарь содержит проектно-сметные термины, типовые орфографические ошибки и OCR-noise признаки.",
    ]
    for issue in issues[:6]:
        steps.append(
            f"{issue.issue_type}: `{issue.matched_text}` -> `{issue.suggestion}`, "
            f"confidence={issue.confidence:.0%}; {issue.explanation}"
        )
        if issue.evidence:
            steps.append(f"Evidence snippet: {issue.evidence}")
    return steps


def _extract_snippets(raw_text: str, terms: tuple[str, ...], *, window: int = 70, limit: int = 3) -> tuple[str, ...]:
    normalized = " ".join(raw_text.split())
    if not normalized:
        return ()

    snippets: list[str] = []
    lowered = normalized.lower()
    for term in terms:
        term_value = term.strip().lower()
        if not term_value:
            continue
        index = lowered.find(term_value)
        if index < 0:
            continue
        start = max(0, index - window)
        end = min(len(normalized), index + len(term_value) + window)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(normalized) else ""
        snippet = f"{prefix}{normalized[start:end]}{suffix}"
        if snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return tuple(snippets)


def _score_group_against_text(
    group: RequiredDocumentGroup,
    *,
    normalized_text: str,
    raw_text: str,
    use_content_patterns: bool,
) -> DocumentTypeEvidence | None:
    patterns = group.content_patterns if use_content_patterns else group.patterns
    matched_terms = tuple(pattern for pattern in patterns if _normalize(pattern) in normalized_text)
    if not matched_terms:
        return None

    coverage = len(matched_terms) / max(1, len(patterns))
    exact_bonus = 0.18 if any(len(_normalize(term)) >= 12 for term in matched_terms) else 0.0
    density_bonus = min(0.16, len(matched_terms) * 0.04)
    score = _clamp(0.46 + coverage * 0.34 + exact_bonus + density_bonus, 0.0, 1.0)
    return DocumentTypeEvidence(
        group=group,
        score=score,
        matched_terms=matched_terms,
        snippets=_extract_snippets(raw_text, matched_terms),
    )


def _best_group_evidence(
    text: str,
    *,
    groups: tuple[RequiredDocumentGroup, ...],
    use_content_patterns: bool,
) -> DocumentTypeEvidence | None:
    normalized_text = _normalize(text)
    candidates = [
        evidence
        for group in groups
        if (
            evidence := _score_group_against_text(
                group,
                normalized_text=normalized_text,
                raw_text=text,
                use_content_patterns=use_content_patterns,
            )
        )
        is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.score)


def _safe_parse_llm_json(raw_response: str | None) -> dict[str, object] | None:
    if not raw_response:
        return None
    response = raw_response.strip()
    try:
        payload = json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response, flags=re.DOTALL)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _llm_classify_document_type(
    document: Document,
    *,
    profile: EstimateRulesProfile,
) -> tuple[str | None, float | None, str | None]:
    provider = get_llm_provider()
    if provider.provider_name == "template-fallback":
        return None, None, None

    allowed_labels = ", ".join(group.key for group in profile.required_groups)
    prompt = (
        "Определи тип документа для проверки достоверности сметной стоимости. "
        "Верни только JSON без поясняющего текста: "
        '{"label": "<one_of_allowed_or_unknown>", "confidence": 0.0, "reason": "short"}.\n\n'
        f"Разрешенные label: {allowed_labels}, unknown.\n"
        f"Нормативный профиль: {profile.regulation_label}.\n"
        f"Имя файла: {document.relative_path or document.file_name}\n"
        f"Текстовый фрагмент:\n{(document.extracted_text or '')[:2200]}"
    )
    response = provider.complete(
        prompt,
        system=(
            "Ты классификатор проектно-сметных документов. "
            "Не выдумывай факты, используй только имя файла и переданный текст."
        ),
        max_tokens=180,
    )
    payload = _safe_parse_llm_json(response)
    if not payload:
        return None, None, None

    label = payload.get("label")
    confidence = payload.get("confidence")
    reason = payload.get("reason")
    label_value = str(label).strip() if label is not None else None
    if label_value not in {group.key for group in profile.required_groups}:
        label_value = None
    try:
        confidence_value = _clamp(float(confidence), 0.0, 1.0) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None
    reason_value = str(reason).strip()[:300] if reason is not None else None
    return label_value, confidence_value, reason_value


def _classify_document_type(document: Document, *, profile: EstimateRulesProfile) -> DocumentTypeClassification:
    name_text = f"{document.relative_path or ''} {document.file_name} {document.original_file_name or ''}"
    content_text = document.extracted_text or ""
    name_evidence = _best_group_evidence(name_text, groups=profile.required_groups, use_content_patterns=False)
    content_evidence = _best_group_evidence(content_text, groups=profile.required_groups, use_content_patterns=True)
    llm_label, llm_confidence, llm_reason = _llm_classify_document_type(document, profile=profile)

    evidence_by_key = {
        evidence.group.key: evidence
        for evidence in (name_evidence, content_evidence)
        if evidence is not None
    }
    if llm_label and llm_label in evidence_by_key:
        predicted_group = evidence_by_key[llm_label].group
        confidence = _clamp(((llm_confidence or 0.72) * 0.45) + (evidence_by_key[llm_label].score * 0.55), 0.0, 0.98)
        return DocumentTypeClassification(
            predicted_group=predicted_group,
            confidence=confidence,
            method="rules+llm",
            name_evidence=name_evidence,
            content_evidence=content_evidence,
            llm_label=llm_label,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
        )

    if content_evidence is not None and name_evidence is not None and content_evidence.group.key == name_evidence.group.key:
        confidence = _clamp((content_evidence.score * 0.62) + (name_evidence.score * 0.38), 0.0, 0.96)
        method = "rules+llm" if llm_label else "hybrid-rules"
        return DocumentTypeClassification(
            predicted_group=content_evidence.group,
            confidence=confidence,
            method=method,
            name_evidence=name_evidence,
            content_evidence=content_evidence,
            llm_label=llm_label,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
        )

    strongest = max(
        (evidence for evidence in (content_evidence, name_evidence) if evidence is not None),
        key=lambda item: item.score,
        default=None,
    )
    return DocumentTypeClassification(
        predicted_group=strongest.group if strongest is not None else None,
        confidence=_clamp(strongest.score if strongest is not None else 0.0, 0.0, 0.86),
        method="rules+llm" if llm_label else "hybrid-rules",
        name_evidence=name_evidence,
        content_evidence=content_evidence,
        llm_label=llm_label,
        llm_confidence=llm_confidence,
        llm_reason=llm_reason,
    )


def _format_evidence(evidence: DocumentTypeEvidence | None) -> str:
    if evidence is None:
        return "не определено"
    return f"{evidence.group.title} ({evidence.score:.0%})"


def _format_terms(evidence: DocumentTypeEvidence | None) -> str:
    if evidence is None or not evidence.matched_terms:
        return "нет устойчивых маркеров"
    return ", ".join(evidence.matched_terms[:5])


def _format_snippets(evidence: DocumentTypeEvidence | None) -> list[str]:
    if evidence is None or not evidence.snippets:
        return []
    return [f"Evidence snippet: {snippet}" for snippet in evidence.snippets[:3]]


def _completeness_severity(group: RequiredDocumentGroup) -> str:
    if group.required_level == "mandatory":
        return "danger"
    if group.required_level == "recommended":
        return "warning"
    return "info"


def _required_level_label(group: RequiredDocumentGroup) -> str:
    return {
        "mandatory": "обязательная группа базового профиля",
        "recommended": "рекомендуемая группа сметного профиля",
        "conditional": "условная группа, применимая при наличии соответствующего основания",
    }.get(group.required_level, group.required_level)


PP87_GENERIC_TEXT_REQUIREMENTS = (
    (
        "сведения об объекте",
        ("объект", "строительство", "реконструкция", "капитальный ремонт", "снос", "здание", "сооружение"),
    ),
    (
        "описание принятых технических и иных решений",
        ("решение", "мероприятие", "техническ", "проектн", "конструктивн", "инженерн", "технологическ"),
    ),
    (
        "ссылки на нормативные/технические документы или исходные данные",
        ("гост", "сп ", "снип", "техническ", "услов", "исходн", "задание", "гпзу", "изыскан"),
    ),
    (
        "расчеты или обоснование принятых решений",
        ("расчет", "расчёт", "обоснован", "показател", "параметр", "значени", "таблиц"),
    ),
)

PP87_SECTION_SPECIFIC_REQUIREMENTS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "land_plot_planning_scheme": (
        ("сведения о земельном участке и планировочных решениях", ("земельн", "участ", "границ", "планировочн")),
        ("графическая схема/план", ("схема", "план", "чертеж", "чертёж")),
    ),
    "architectural_solutions": (
        ("объемно-планировочные или архитектурные решения", ("архитектур", "фасад", "план", "объемно", "объёмно")),
        ("графические материалы архитектурного раздела", ("чертеж", "чертёж", "план", "схема", "фасад")),
    ),
    "structural_solutions": (
        ("конструктивные решения и несущие элементы", ("конструктив", "несущ", "фундамент", "каркас", "перекрыт")),
    ),
    "engineering_equipment_networks": (
        ("инженерные сети и технические решения", ("инженер", "сети", "оборудован", "водоснабж", "электроснабж", "отоплен")),
    ),
    "construction_organization_project": (
        ("организация строительства", ("организация строительства", "стройплощад", "календар", "пос")),
    ),
    "fire_safety": (
        ("мероприятия пожарной безопасности", ("пожар", "эвакуац", "огнестойк", "пожаротуш")),
    ),
    "construction_estimate": (
        ("сметная документация", ("смет", "локальн", "сводн", "стоимост", "итого", "расчет", "расчёт")),
    ),
}


def _document_identity_text(document: Document) -> str:
    return f"{document.relative_path or ''} {document.file_name} {document.original_file_name or ''}"


def _text_has_any(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    return any(_normalize(pattern) in normalized for pattern in patterns)


def _format_missing_requirements(missing: list[str]) -> str:
    return "; ".join(missing[:5])


def _build_pp87_section_content_findings(documents: list[Document], *, profile: EstimateRulesProfile = PP87_RULES_PROFILE) -> list[dict]:
    findings: list[dict] = []
    classifications = {document.id: _classify_document_type(document, profile=profile) for document in documents}

    for document in documents:
        classification = classifications[document.id]
        group = classification.predicted_group
        source_ref = document.relative_path or document.file_name
        content = document.extracted_text or ""
        identity = _document_identity_text(document)
        combined = f"{identity}\n{content}"

        if group is None:
            findings.append(
                {
                    "stage_key": "section_content",
                    "document_id": document.id,
                    "title": "Не определен раздел проектной документации по ПП 87",
                    "description": (
                        "Файл не удалось устойчиво отнести к разделу проектной документации по ПП РФ N 87. "
                        "Проверка содержания такого файла ограничена."
                    ),
                    "severity": "warning",
                    "confidence_score": 0.66,
                    "normative_basis": "ПП РФ N 87: состав и требования к содержанию разделов проектной документации",
                    "source_ref": source_ref,
                    "recommendation": "Проверь название файла, титульный лист и структуру раздела; при необходимости переименуй или загрузи корректный раздел.",
                    "xai_json": [
                        f"Нормативный профиль: {profile.regulation_label}.",
                        "Проверены имя файла, относительный путь и извлеченный текст.",
                        "Маркеры разделов ПП 87 не дали устойчивого совпадения.",
                        f"Метод классификации: {classification.method}; confidence={classification.confidence:.0%}.",
                    ],
                }
            )
            continue

        if not content.strip():
            findings.append(
                {
                    "stage_key": "section_content",
                    "document_id": document.id,
                    "title": "Нет текстового слоя для проверки содержания раздела ПП 87",
                    "description": (
                        f"Файл классифицирован как `{group.title}`, но extracted_text пустой. "
                        "Невозможно проверить текстовую часть раздела по ПП РФ N 87."
                    ),
                    "severity": "warning",
                    "confidence_score": _clamp(classification.confidence, 0.62, 0.84),
                    "normative_basis": f"{group.normative_basis}; общие требования ПП РФ N 87 к текстовой части проектной документации",
                    "source_ref": source_ref,
                    "recommendation": "Загрузи версию с текстовым слоем или улучши OCR, чтобы проверить содержание раздела.",
                    "xai_json": [
                        f"Предполагаемый раздел: {group.title}.",
                        f"Основание классификации: {_format_evidence(classification.name_evidence)} / {_format_evidence(classification.content_evidence)}.",
                        "Текстовый слой пустой, поэтому признаки описания решений, ссылок на НТД и расчетов не проверяются.",
                    ],
                }
            )
            continue

        missing_generic = [
            label
            for label, patterns in PP87_GENERIC_TEXT_REQUIREMENTS
            if not _text_has_any(combined, patterns)
        ]
        section_requirements = PP87_SECTION_SPECIFIC_REQUIREMENTS.get(group.key, ())
        missing_specific = [
            label
            for label, patterns in section_requirements
            if not _text_has_any(combined, patterns)
        ]
        missing = [*missing_generic, *missing_specific]
        if not missing:
            continue

        severity = "danger" if group.key == "construction_estimate" and any("смет" in item for item in missing) else "warning"
        confidence = _clamp(0.58 + min(0.28, len(missing) * 0.07) + classification.confidence * 0.12, 0.62, 0.9)
        findings.append(
            {
                "stage_key": "section_content",
                "document_id": document.id,
                "title": "Содержание раздела требует проверки по ПП 87",
                "description": (
                    f"Файл похож на раздел `{group.title}`, но в тексте/имени не найдены признаки: "
                    f"{_format_missing_requirements(missing)}."
                ),
                "severity": severity,
                "confidence_score": confidence,
                "normative_basis": f"{group.normative_basis}; общие требования ПП РФ N 87 к текстовой/графической части проектной документации",
                "source_ref": source_ref,
                "recommendation": (
                    "Проверь раздел вручную: возможно, нужные сведения находятся в графической части, другом томе или плохо извлечены OCR. "
                    "Если раздел действительно неполный, загрузи корректную версию."
                ),
                "xai_json": [
                    f"Предполагаемый раздел ПП 87: {group.title}.",
                    f"Метод классификации: {classification.method}; confidence={classification.confidence:.0%}.",
                    f"Нормативная привязка: {group.normative_basis}.",
                    "Проверены общие признаки текстовой части: сведения об объекте, описание решений, ссылки на НТД/исходные данные, расчеты.",
                    "Проверены section-specific маркеры для найденного раздела.",
                    f"Не найдены признаки: {_format_missing_requirements(missing)}.",
                    *_format_snippets(classification.content_evidence),
                ],
            }
        )

    return findings[:14]


def _build_filename_findings(documents: list[Document], *, profile: EstimateRulesProfile = PP145_RULES_PROFILE) -> list[dict]:
    findings: list[dict] = []
    classifications = {document.id: _classify_document_type(document, profile=profile) for document in documents}
    for document in documents:
        classification = classifications[document.id]
        name_evidence = classification.name_evidence
        content_evidence = classification.content_evidence
        if (
            name_evidence is not None
            and content_evidence is not None
            and name_evidence.group.key != content_evidence.group.key
        ):
            xai_steps = [
                f"Метод классификации: {classification.method}; confidence итогового типа: {classification.confidence:.0%}.",
                f"По имени файл похож на: {_format_evidence(name_evidence)}; маркеры: {_format_terms(name_evidence)}.",
                f"По извлеченному тексту файл похож на: {_format_evidence(content_evidence)}; маркеры: {_format_terms(content_evidence)}.",
                "Пересечения между типом по имени и типом по содержанию не найдено.",
                "Итог: тип по имени и тип по содержанию различаются, поэтому файл требует решения пользователя.",
            ]
            if classification.llm_label:
                xai_steps.append(
                    f"LLM-классификатор предложил label `{classification.llm_label}`"
                    f" с confidence {classification.llm_confidence:.0%}." if classification.llm_confidence is not None else
                    f"LLM-классификатор предложил label `{classification.llm_label}`."
                )
            if classification.llm_reason:
                xai_steps.append(f"Краткое пояснение LLM: {classification.llm_reason}.")
            xai_steps.extend(_format_snippets(content_evidence))
            findings.append(
                {
                    "stage_key": "filename_content",
                    "document_id": document.id,
                    "title": "Название файла не совпадает с извлеченным содержанием",
                    "description": (
                        f"По имени файл похож на: {name_evidence.group.title}. "
                        f"По извлеченному тексту он похож на: {content_evidence.group.title}. "
                        f"Confidence классификации: {classification.confidence:.0%}."
                    ),
                    "severity": "danger",
                    "confidence_score": _clamp(max(name_evidence.score, content_evidence.score, classification.confidence), 0.72, 0.94),
                    "normative_basis": (
                        f"{profile.regulation_label} и профиль EvidenceXAI: состав комплекта должен быть трассируемым, "
                        "а имя файла должно соответствовать фактическому типу документа"
                    ),
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Переименуй файл, замени документ или одобри расхождение вручную, если это допустимо для внутренней структуры комплекта.",
                    "xai_json": xai_steps,
                }
            )

    weak_document = next(
        (
            document
            for document in documents
            if classifications[document.id].name_evidence is None
        ),
        None,
    )
    if weak_document is None:
        return findings

    weak_classification = classifications[weak_document.id]
    weak_content_evidence = weak_classification.content_evidence

    findings.append(
        {
            "stage_key": "filename_content",
            "document_id": weak_document.id,
            "title": "Название файла требует проверки",
            "description": (
                "В названии файла не найден понятный признак типа сметного документа. Система сравнивает название "
                "с содержанием документа: заголовками, первыми страницами и извлеченным текстом."
            ),
            "severity": "warning",
            "confidence_score": _clamp(max(weak_classification.confidence, 0.62), 0.62, 0.82),
            "normative_basis": f"{profile.regulation_label} и правило EvidenceXAI: имя файла должно отражать фактический тип документа для трассируемой подачи",
            "source_ref": weak_document.relative_path or weak_document.file_name,
            "recommendation": "Проверь название файла или одобри его вручную, если внутри документа корректный сметный материал.",
            "xai_json": [
                f"Метод классификации: {weak_classification.method}; confidence: {weak_classification.confidence:.0%}.",
                "Имя файла нормализовано: удалены технические разделители и версия.",
                "После нормализации в имени не найдено маркеров ЛСР, ССР, смета, пояснительная записка или коммерческое предложение.",
                f"По содержанию предполагаемый тип: {_format_evidence(weak_content_evidence)}.",
                "Вывод не является юридическим отказом: это сигнал для ручной проверки соответствия названия содержанию.",
                *_format_snippets(weak_content_evidence),
            ],
        }
    )
    return findings


def _build_completeness_findings(documents: list[Document], *, profile: EstimateRulesProfile = PP145_RULES_PROFILE) -> list[dict]:
    findings: list[dict] = []
    for group in profile.required_groups:
        if _has_required_group(documents, group.patterns + group.content_patterns):
            continue
        severity = _completeness_severity(group)
        findings.append(
            {
                "stage_key": "completeness",
                "document_id": None,
                "title": f"Не найден документ: {group.title}",
                "description": (
                    f"В выбранной папке нет файла, который по названию или тексту похож на группу `{group.title}`. "
                    f"Статус группы: {_required_level_label(group)}."
                ),
                "severity": severity,
                "confidence_score": {"danger": 0.86, "warning": 0.78, "info": 0.68}[severity],
                "normative_basis": group.normative_basis,
                "source_ref": "Список файлов выбранной папки",
                "recommendation": (
                    "Загрузи недостающий документ, свяжи существующий файл с этим пунктом или отметь пункт "
                    "как неприменимый для конкретного объекта."
                ),
                "xai_json": [
                    f"Ожидаемая группа: {group.title}.",
                    f"Статус группы: {_required_level_label(group)}.",
                    f"Нормативная привязка: {group.normative_basis}.",
                    f"Проверенные маркеры имени: {', '.join(group.patterns)}.",
                    f"Проверенные маркеры текста: {', '.join(group.content_patterns)}.",
                    f"Проверено документов: {len(documents)}.",
                    "Система не нашла устойчивого совпадения среди выбранных обработанных документов.",
                    "Вывод является предварительной машинной проверкой комплектности и требует внутренней нормативной проверки rules pack для production.",
                ],
            }
        )
    return findings


def _build_quality_findings(documents: list[Document], *, profile: EstimateRulesProfile = PP145_RULES_PROFILE) -> list[dict]:
    findings: list[dict] = []
    for document in documents:
        content = _document_content_text(document)
        density = _text_density_per_page(document, content)
        visual_document = _is_visual_document(document)
        image_document = _is_image_document(document)
        visual_detection = detect_visual_signature_or_seal(document.storage_path) if visual_document else None
        visual_quality = assess_visual_quality(document.storage_path) if visual_document else None
        if visual_quality is not None and visual_quality.available and visual_quality.issue_keys:
            issue_labels = [_visual_quality_issue_label(issue_key) for issue_key in visual_quality.issue_keys]
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Визуальное качество документа требует проверки",
                    "description": (
                        "Локальный visual quality baseline нашел признаки, которые могут ухудшить OCR и экспертную "
                        f"проверку: {', '.join(issue_labels)}."
                    ),
                    "severity": "warning",
                    "confidence_score": _clamp(visual_quality.confidence, 0.0, 0.9),
                    "normative_basis": f"{profile.regulation_label} и профиль качества EvidenceXAI: документы должны быть читаемыми и пригодными для машинной и экспертной проверки",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Проверь исходный скан и при необходимости загрузи файл с лучшим разрешением, контрастом или текстовым слоем.",
                    "xai_json": [
                        "Проверка выполнена локально внутри backend/worker runtime, без отправки документа во внешний OCR/vision API.",
                        "Оценены разрешение страницы, контраст, резкость, доля темных и светлых пикселей.",
                        *_visual_quality_steps(visual_quality),
                    ],
                }
            )
        if not content.strip():
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Не найден извлеченный текстовый слой",
                    "description": "Документ обработан, но извлеченный текст пустой. Для экспертизы потребуется OCR/vision-проверка качества страниц.",
                    "severity": "warning",
                    "confidence_score": 0.86,
                    "normative_basis": f"{profile.regulation_label} и профиль EvidenceXAI: документы должны быть пригодны для читаемой машинной и экспертной проверки",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Загрузи версию с текстовым слоем или проверь качество скана перед подачей.",
                    "xai_json": [
                        "Статус документа позволяет включить его в workflow.",
                        "Поле extracted_text пустое, поэтому evidence linking и орфографическая проверка ограничены.",
                        "Вывод помечен как warning, потому что OCR/vision контур может восстановить текст в следующей фазе.",
                        *(_visual_quality_steps(visual_quality) if visual_quality is not None else []),
                        *(_visual_detection_steps(visual_detection) if visual_detection is not None else []),
                    ],
                }
            )
            if visual_detection is None or not (visual_detection.signature_like or visual_detection.seal_like):
                continue

        if visual_document and density < 18:
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Низкая плотность извлеченного текста",
                    "description": (
                        f"Документ похож на визуальный источник, но на страницу приходится примерно {density:.1f} "
                        "распознанных токенов. Это может означать скан низкого качества, титульный лист без текста "
                        "или неполное OCR-распознавание."
                    ),
                    "severity": "warning",
                    "confidence_score": 0.78 if image_document else 0.72,
                    "normative_basis": f"{profile.regulation_label} и профиль качества EvidenceXAI: документы должны быть читаемыми и пригодными для машинной и экспертной проверки",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Проверь качество скана и при необходимости загрузи файл с текстовым слоем или более высоким разрешением.",
                    "xai_json": [
                        f"Тип источника: {'изображение' if image_document else 'PDF/визуальный документ'}.",
                        f"Страниц: {document.page_count or 1}.",
                        f"Распознанных токенов: {_word_count(content)}.",
                        f"Плотность текста на страницу: {density:.1f}.",
                        "Порог baseline: меньше 18 токенов на страницу считается слабым OCR/text layer сигналом.",
                        "Это не юридический отказ: вывод указывает на необходимость визуальной проверки качества.",
                        *(_visual_quality_steps(visual_quality) if visual_quality is not None else []),
                        *(_visual_detection_steps(visual_detection) if visual_detection is not None else []),
                    ],
                }
            )

        terminology_issues = assess_terminology_quality(document.extracted_text or "")
        if terminology_issues:
            issue_labels = [issue.matched_text.lower() for issue in terminology_issues[:4]]
            issue_types = {issue.issue_type for issue in terminology_issues}
            confidence = max(issue.confidence for issue in terminology_issues)
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Найдены подозрительные орфографические ошибки",
                    "description": (
                        "Локальный словарь проектно-сметной терминологии нашел сигналы "
                        f"({', '.join(sorted(issue_types))}): {', '.join(issue_labels)}."
                    ),
                    "severity": "warning",
                    "confidence_score": _clamp(confidence, 0.62, 0.9),
                    "normative_basis": f"{profile.regulation_label} и профиль качества EvidenceXAI: текст сметного комплекта должен быть читаемым и не содержать явных технических/орфографических ошибок",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Проверь фрагмент в исходном файле: это может быть реальная ошибка, терминологическое отклонение или OCR-noise.",
                    "xai_json": [
                        "Текст документа проверен локальным словарем проектно-сметной терминологии.",
                        "Вывод требует ручной проверки, потому что часть таких сигналов может быть шумом OCR или допустимой внутренней терминологией.",
                        *_terminology_issue_steps(terminology_issues),
                    ],
                }
            )

        visual_verified = visual_detection is not None and (visual_detection.signature_like or visual_detection.seal_like)
        if not any(marker in content for marker in SIGNATURE_MARKERS) and visual_verified:
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Визуальные признаки подписи или печати найдены",
                    "description": "Layout-aware baseline нашел signature/seal-like компоненты, хотя в тексте нет маркеров подписи или печати.",
                    "severity": "info",
                    "confidence_score": _clamp(visual_detection.confidence, 0.0, 0.88),
                    "normative_basis": f"{profile.regulation_label} и профиль EvidenceXAI: подаваемый комплект должен быть оформлен и пригоден для проверки подписных блоков",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Проверь найденную область вручную; baseline фиксирует визуальный признак, но не подтверждает подлинность подписи или печати.",
                    "xai_json": [
                        "Текстовые маркеры подписи/печати не найдены.",
                        "Визуальный baseline нашел signature/seal-like компонент в нижней части страницы.",
                        "Это предварительный XAI-сигнал по layout, а не проверка подлинности подписи или печати.",
                        *_visual_detection_steps(visual_detection),
                    ],
                }
            )
        elif not any(marker in content for marker in SIGNATURE_MARKERS):
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": "Не найдены текстовые признаки подписи или печати",
                    "description": "В извлеченном тексте нет маркеров подписи, печати, М.П., ГИП или утверждения.",
                    "severity": "info",
                    "confidence_score": 0.62,
                    "normative_basis": f"{profile.regulation_label} и профиль EvidenceXAI: подаваемый комплект должен быть оформлен и пригоден для проверки полномочий/подписных блоков",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Проверь визуально наличие подписи/печати; финальное подтверждение требует OCR/vision detector.",
                    "xai_json": [
                        "Проверены только текстовые маркеры подписи и печати.",
                        "В тексте не найдено слов: подпись, печать, М.П., ГИП, утверждаю, директор.",
                        "Это не доказывает отсутствие подписи на изображении; нужен layout-aware vision контур.",
                        *(_visual_detection_steps(visual_detection) if visual_detection is not None else []),
                    ],
                }
            )
        elif visual_document:
            visual_detection_steps = _visual_detection_steps(visual_detection) if visual_detection is not None else []
            findings.append(
                {
                    "stage_key": "quality_spell_signature",
                    "document_id": document.id,
                    "title": (
                        "Визуальные признаки подписи или печати найдены"
                        if visual_verified
                        else "Текстовые признаки подписи или печати найдены"
                    ),
                    "description": (
                        "Layout-aware baseline нашел визуальные signature/seal-like компоненты и текстовые маркеры подписи/печати."
                        if visual_verified
                        else "В извлеченном тексте найдены маркеры подписи, печати, М.П., ГИП, утверждения или роли подписанта."
                    ),
                    "severity": "info",
                    "confidence_score": _clamp(max(0.66, visual_detection.confidence if visual_detection else 0.0), 0.0, 0.88),
                    "normative_basis": f"{profile.regulation_label} и профиль EvidenceXAI: подаваемый комплект должен быть оформлен и пригоден для проверки подписных блоков",
                    "source_ref": document.relative_path or document.file_name,
                    "recommendation": "Для production-подтверждения нужен vision detector страницы, координат подписи/печати и уверенности распознавания.",
                    "xai_json": [
                        "Проверены текстовые маркеры подписи и печати.",
                        "Найден хотя бы один маркер: подпись, печать, М.П., ГИП, утверждаю или директор.",
                        (
                            "Baseline нашел визуальный признак на странице, но это не является проверкой подлинности подписи или печати."
                            if visual_verified
                            else "Baseline подтверждает только текстовый признак; визуальная валидность подписи/печати пока не доказывается."
                        ),
                        "Для строгой проверки нужен vision detector с координатами подписи/печати на странице.",
                        *visual_detection_steps,
                    ],
                }
            )

    return findings[:12]


def _create_empty_workflow(db: Session, report: Report, documents: list[Document], *, profile: EstimateRulesProfile) -> ExpertiseWorkflow:
    workflow = ExpertiseWorkflow(
        organization_id=report.organization_id,
        report_id=report.id,
        status="queued",
        progress=0,
        eta_seconds=int(max(1, len(documents)) * 2.4 * 60),
        checked_files=0,
        total_files=len(documents),
        unresolved_findings=0,
        current_stage_key="start",
        model_version=MODEL_VERSION,
        rule_version=profile.rule_version,
        state_json={
            "source": "celery_stage_pipeline",
            "rules_profile": profile.key,
            "regulation": profile.regulation_label,
            "created_from_selected_document_ids": report.selected_document_ids,
        },
    )
    db.add(workflow)
    db.flush()
    for index, definition in enumerate(profile.stage_definitions):
        db.add(
            ExpertiseWorkflowStage(
                organization_id=report.organization_id,
                workflow_id=workflow.id,
                stage_key=definition.key,
                title=definition.title,
                short_title=definition.short_title,
                order_number=index + 1,
                status="pending",
                progress=0,
                checked_files=0,
                total_files=len(documents),
                findings_count=0,
                summary_json={},
            )
        )
    db.commit()
    db.refresh(workflow)
    return workflow


def _workflow_has_findings(db: Session, workflow: ExpertiseWorkflow) -> bool:
    return db.scalar(select(ExpertiseFinding.id).where(ExpertiseFinding.workflow_id == workflow.id).limit(1)) is not None


def ensure_estimate_expertise_workflow(db: Session, report: Report, *, reset_outdated: bool = True) -> ExpertiseWorkflow:
    profile = _rules_profile_for_report(report)
    workflow = db.scalar(select(ExpertiseWorkflow).where(ExpertiseWorkflow.report_id == report.id))
    if workflow is not None:
        if reset_outdated and (workflow.model_version != MODEL_VERSION or workflow.rule_version != profile.rule_version):
            if workflow.status in PIPELINE_ACTIVE_STATUSES:
                recalculate_workflow_metrics(db, workflow)
                db.commit()
                db.refresh(workflow)
                return workflow
            db.delete(workflow)
            db.commit()
        else:
            recalculate_workflow_metrics(db, workflow)
            db.commit()
            db.refresh(workflow)
            return workflow

    documents = _load_workflow_documents(db, report)
    return _create_empty_workflow(db, report, documents, profile=profile)


def mark_workflow_start_queued(db: Session, workflow: ExpertiseWorkflow) -> None:
    report = db.scalar(select(Report).where(Report.id == workflow.report_id))
    workflow.status = "running"
    workflow.current_stage_key = "start"
    workflow.progress = max(float(workflow.progress or 0), 1.0)
    workflow.state_json = {
        **(workflow.state_json or {}),
        "start_task_queued_at": datetime.now(UTC).isoformat(),
    }
    db.add(workflow)
    if report is not None and report.status not in REPORT_STATUS_LOCKED_BY_USER:
        report.status = ReportStatus.analyzing
        report.readiness_percent = max(float(report.readiness_percent or 0), 12.0)
        db.add(report)
    db.commit()


def workflow_needs_pipeline_run(db: Session, workflow: ExpertiseWorkflow) -> bool:
    if workflow.status == "queued":
        return True
    if workflow.status == "blocked" and not _workflow_has_findings(db, workflow):
        return True
    return False


def run_estimate_expertise_pipeline(db: Session, report_id: str) -> ExpertiseWorkflow:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise ValueError("Report not found")
    profile = _rules_profile_for_report(report)
    workflow = ensure_estimate_expertise_workflow(db, report, reset_outdated=False)
    if workflow.model_version != MODEL_VERSION or workflow.rule_version != profile.rule_version:
        workflow = ensure_estimate_expertise_workflow(db, report, reset_outdated=False)

    documents = _load_workflow_documents(db, report)
    workflow.status = "running"
    workflow.model_version = MODEL_VERSION
    workflow.rule_version = profile.rule_version
    workflow.total_files = len(documents)
    workflow.current_stage_key = "start"
    workflow.checked_files = 0
    workflow.unresolved_findings = 0
    workflow.progress = 0
    workflow.eta_seconds = int((len(documents) * 2.4 + 3.5) * 60)
    db.add(workflow)
    db.execute(delete(ExpertiseUserDecision).where(ExpertiseUserDecision.workflow_id == workflow.id))
    db.execute(delete(ExpertiseFinding).where(ExpertiseFinding.workflow_id == workflow.id))
    db.commit()

    _run_start_stage(db, workflow, documents)
    if documents:
        _advance_workflow_until_blocked_or_complete(db, workflow)
    else:
        _run_final_stage(db, workflow)
    recalculate_workflow_metrics(db, workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def _get_stage(db: Session, workflow: ExpertiseWorkflow, stage_key: str) -> ExpertiseWorkflowStage:
    stage = db.scalar(
        select(ExpertiseWorkflowStage).where(
            ExpertiseWorkflowStage.workflow_id == workflow.id,
            ExpertiseWorkflowStage.stage_key == stage_key,
        )
    )
    if stage is None:
        profile = _rules_profile_for_workflow(workflow)
        definition = _stage_definition(stage_key, profile=profile)
        stage = ExpertiseWorkflowStage(
            organization_id=workflow.organization_id,
            workflow_id=workflow.id,
            stage_key=definition.key,
            title=definition.title,
            short_title=definition.short_title,
            order_number=next(index + 1 for index, item in enumerate(profile.stage_definitions) if item.key == stage_key),
            status="pending",
            progress=0,
            checked_files=0,
            total_files=workflow.total_files,
            findings_count=0,
            summary_json={},
        )
        db.add(stage)
        db.flush()
    return stage


def _mark_stage_running(db: Session, workflow: ExpertiseWorkflow, stage: ExpertiseWorkflowStage) -> None:
    workflow.status = "running"
    workflow.current_stage_key = stage.stage_key
    stage.status = "running"
    stage.progress = max(stage.progress, 12)
    db.add(workflow)
    db.add(stage)
    db.commit()


def _run_start_stage(db: Session, workflow: ExpertiseWorkflow, documents: list[Document]) -> None:
    stage = _get_stage(db, workflow, "start")
    _mark_stage_running(db, workflow, stage)
    stage.total_files = len(documents)
    stage.checked_files = len(documents)
    stage.status = "completed" if documents else "blocked"
    stage.progress = 100 if documents else 0
    stage.summary_json = {
        "selected_ready_documents": len(documents),
        "validation": "ok" if documents else "no_ready_documents",
    }
    workflow.total_files = len(documents)
    workflow.checked_files = len(documents)
    db.add(stage)
    db.add(workflow)
    db.commit()


def _run_analysis_stage(
    db: Session,
    workflow: ExpertiseWorkflow,
    stage_key: str,
    seeds: list[dict],
    documents: list[Document],
) -> None:
    stage = _get_stage(db, workflow, stage_key)
    _mark_stage_running(db, workflow, stage)
    for seed in seeds:
        db.add(
            ExpertiseFinding(
                organization_id=workflow.organization_id,
                report_id=workflow.report_id,
                workflow_id=workflow.id,
                stage_id=stage.id,
                document_id=seed["document_id"],
                stage_key=seed["stage_key"],
                title=seed["title"],
                description=seed["description"],
                severity=seed["severity"],
                confidence_score=seed["confidence_score"],
                normative_basis=seed["normative_basis"],
                source_ref=seed["source_ref"],
                recommendation=seed["recommendation"],
                xai_json=seed["xai_json"],
                status="open",
                replacement_progress=0,
            )
        )
    stage.findings_count = len(seeds)
    stage.total_files = len(documents)
    stage.checked_files = len(documents)
    stage.progress = 100
    stage.status = "blocked" if any(seed["severity"] != "info" for seed in seeds) else "completed"
    stage.summary_json = {
        "generated_findings": len(seeds),
        "danger": sum(1 for seed in seeds if seed["severity"] == "danger"),
        "warning": sum(1 for seed in seeds if seed["severity"] == "warning"),
        "info": sum(1 for seed in seeds if seed["severity"] == "info"),
    }
    db.add(stage)
    db.commit()


def _analysis_stage_keys(profile: EstimateRulesProfile) -> list[str]:
    return [
        definition.key
        for definition in profile.stage_definitions
        if definition.key not in {"start", "final"}
    ]


def _build_stage_findings(stage_key: str, documents: list[Document], *, profile: EstimateRulesProfile) -> list[dict]:
    if stage_key == "filename_content":
        return _build_filename_findings(documents, profile=profile)
    if stage_key == "completeness":
        return _build_completeness_findings(documents, profile=profile)
    if stage_key == "section_content":
        return _build_pp87_section_content_findings(documents, profile=profile)
    if stage_key == "quality_spell_signature":
        return _build_quality_findings(documents, profile=profile)
    return []


def _stage_has_unresolved_actions(db: Session, workflow: ExpertiseWorkflow, stage_key: str) -> bool:
    return db.scalar(
        select(ExpertiseFinding.id)
        .where(
            ExpertiseFinding.workflow_id == workflow.id,
            ExpertiseFinding.stage_key == stage_key,
            ExpertiseFinding.severity != "info",
            ExpertiseFinding.status.in_(OPEN_STATUSES),
        )
        .limit(1)
    ) is not None


def _advance_workflow_until_blocked_or_complete(db: Session, workflow: ExpertiseWorkflow) -> None:
    report = db.scalar(select(Report).where(Report.id == workflow.report_id))
    if report is None:
        raise ValueError("Report not found")

    profile = _rules_profile_for_report(report)
    documents = _load_workflow_documents(db, report)
    for stage_key in _analysis_stage_keys(profile):
        stage = _get_stage(db, workflow, stage_key)
        if _stage_has_unresolved_actions(db, workflow, stage_key):
            recalculate_workflow_metrics(db, workflow)
            db.commit()
            return
        if stage.status == "completed":
            continue
        if stage.status in {"pending", "running", "blocked"}:
            _run_analysis_stage(
                db,
                workflow,
                stage_key,
                _build_stage_findings(stage_key, documents, profile=profile),
                documents,
            )
            if _stage_has_unresolved_actions(db, workflow, stage_key):
                recalculate_workflow_metrics(db, workflow)
                db.commit()
                return

    _run_final_stage(db, workflow)
    recalculate_workflow_metrics(db, workflow)
    db.commit()


def _run_final_stage(db: Session, workflow: ExpertiseWorkflow) -> None:
    stage = _get_stage(db, workflow, "final")
    _mark_stage_running(db, workflow, stage)
    unresolved_count = db.scalar(
        select(ExpertiseFinding.id)
        .where(
            ExpertiseFinding.workflow_id == workflow.id,
            ExpertiseFinding.severity != "info",
            ExpertiseFinding.status.in_(OPEN_STATUSES),
        )
        .limit(1)
    )
    has_unresolved = unresolved_count is not None
    stage.total_files = workflow.total_files
    stage.checked_files = workflow.total_files if not has_unresolved and workflow.total_files else 0
    stage.progress = 100 if not has_unresolved and workflow.total_files else 0
    stage.status = "completed" if not has_unresolved and workflow.total_files else "pending"
    stage.summary_json = {"ready_for_export": not has_unresolved and workflow.total_files > 0}
    db.add(stage)
    db.commit()


def build_estimate_expertise_workflow_sync(db: Session, report: Report) -> ExpertiseWorkflow:
    """Compatibility helper for old callers: run the stage pipeline synchronously."""
    workflow = ensure_estimate_expertise_workflow(db, report)
    if workflow_needs_pipeline_run(db, workflow):
        return run_estimate_expertise_pipeline(db, report.id)
    return workflow


def recalculate_workflow_metrics(db: Session, workflow: ExpertiseWorkflow) -> None:
    stages = list(db.scalars(select(ExpertiseWorkflowStage).where(ExpertiseWorkflowStage.workflow_id == workflow.id)))
    findings = list(db.scalars(select(ExpertiseFinding).where(ExpertiseFinding.workflow_id == workflow.id)))
    unresolved = [finding for finding in findings if finding.severity != "info" and finding.status in OPEN_STATUSES]
    resolved = [finding for finding in findings if finding.severity != "info" and finding.status not in OPEN_STATUSES]

    stage_by_key = {stage.stage_key: stage for stage in stages}
    start_stage = stage_by_key.get("start")
    pipeline_has_started = bool(
        findings
        or (
            start_stage is not None
            and (start_stage.status != "pending" or start_stage.progress > 0 or start_stage.checked_files > 0)
        )
    )
    if not pipeline_has_started:
        for stage in stages:
            stage.status = "pending"
            stage.progress = 0
            stage.checked_files = 0
            stage.findings_count = 0
            db.add(stage)
        workflow.unresolved_findings = 0
        workflow.checked_files = 0
        workflow.progress = 0
        workflow.status = "blocked" if workflow.total_files == 0 else "queued"
        workflow.current_stage_key = "start"
        db.add(workflow)
        return

    for stage in stages:
        stage_findings = [finding for finding in findings if finding.stage_key == stage.stage_key]
        stage_unresolved = [finding for finding in stage_findings if finding.severity != "info" and finding.status in OPEN_STATUSES]
        if stage.stage_key in ANALYSIS_STAGE_KEYS and stage_unresolved:
            stage.status = "blocked"
            stage.progress = max(stage.progress, 100 if stage_findings else 0)
            stage.checked_files = stage.total_files
        elif stage.stage_key in ANALYSIS_STAGE_KEYS and (stage_findings or stage.status != "pending") and not stage_unresolved:
            stage.status = "completed"
            stage.progress = 100
            stage.checked_files = stage.total_files
        stage.findings_count = len(stage_findings)
        db.add(stage)

    final_stage = stage_by_key.get("final")
    analysis_stages = [stage for stage in stages if stage.stage_key in ANALYSIS_STAGE_KEYS]
    analysis_complete = bool(analysis_stages) and all(stage.status == "completed" for stage in analysis_stages)
    if final_stage is not None and not unresolved and workflow.total_files > 0 and analysis_complete:
        final_stage.status = "completed"
        final_stage.progress = 100
        final_stage.checked_files = final_stage.total_files
        db.add(final_stage)
    elif final_stage is not None and final_stage.status == "completed":
        final_stage.status = "pending"
        final_stage.progress = 0
        final_stage.checked_files = 0
        db.add(final_stage)

    stage_count = max(1, len(stages))
    base_progress = sum(stage.progress / stage_count for stage in stages) if stages else 0
    uplift = (len(resolved) / max(1, len([finding for finding in findings if finding.severity != "info"]))) * 6 if findings else 0
    workflow.unresolved_findings = len(unresolved)
    workflow.checked_files = max((stage.checked_files for stage in stages), default=0)
    workflow.progress = _clamp(round(base_progress + uplift), 0, 100)
    if workflow.total_files == 0 or unresolved:
        workflow.status = "blocked"
    elif stages and all(stage.status == "completed" for stage in stages):
        workflow.status = "completed"
    elif any(stage.status == "running" for stage in stages):
        workflow.status = "running"
    else:
        workflow.status = "queued"
    workflow.current_stage_key = next(
        (stage.stage_key for stage in sorted(stages, key=lambda item: item.order_number) if stage.status in {"running", "blocked", "pending"}),
        "final",
    )
    db.add(workflow)
    _sync_report_readiness_from_workflow(db, workflow)


def _sync_report_readiness_from_workflow(db: Session, workflow: ExpertiseWorkflow) -> None:
    report = db.scalar(select(Report).where(Report.id == workflow.report_id))
    if report is None:
        return

    workflow_progress = _clamp(round(workflow.progress), 0, 100)
    if workflow.status == "completed":
        report.readiness_percent = 100.0
        if report.status not in REPORT_STATUS_LOCKED_BY_USER:
            report.status = ReportStatus.requires_review
    elif workflow.status in PIPELINE_ACTIVE_STATUSES:
        report.readiness_percent = max(float(report.readiness_percent or 0), float(workflow_progress), 12.0)
        if report.status not in REPORT_STATUS_LOCKED_BY_USER:
            report.status = ReportStatus.analyzing
    elif workflow.status == "blocked":
        report.readiness_percent = max(float(workflow_progress), 12.0)
        if report.status not in REPORT_STATUS_LOCKED_BY_USER:
            report.status = ReportStatus.requires_review

    db.add(report)


def record_finding_decision(
    db: Session,
    finding: ExpertiseFinding,
    *,
    user_id: str | None,
    decision_type: str,
    comment: str | None = None,
    replacement_document: Document | None = None,
) -> ExpertiseWorkflow:
    status_by_decision = {
        "approve": "approved",
        "skip": "skipped",
        "replacement": "replacement_resolved",
    }
    finding.status = {
        "approve": "approved_by_user",
        "skip": "skipped_by_user",
        "replacement": "replacement_resolved",
    }[decision_type]
    finding.user_decision_status = status_by_decision[decision_type]
    if replacement_document is not None:
        finding.replacement_document_id = replacement_document.id
        finding.replacement_file_name = replacement_document.file_name
        finding.replacement_progress = 100

    decision = ExpertiseUserDecision(
        organization_id=finding.organization_id,
        workflow_id=finding.workflow_id,
        finding_id=finding.id,
        user_id=user_id,
        decision_type=decision_type,
        comment=comment,
        replacement_document_id=replacement_document.id if replacement_document else None,
        replacement_file_name=replacement_document.file_name if replacement_document else None,
        replacement_progress=100 if replacement_document else 0,
        payload_json={
            "source": "backend_skeleton",
            "decision_status": status_by_decision[decision_type],
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(finding)
    db.add(decision)
    log_action(
        db,
        action=f"estimate_expertise_finding_{status_by_decision[decision_type]}",
        entity_type="expertise_finding",
        entity_id=finding.id,
        organization_id=finding.organization_id,
        user_id=user_id,
        details={
            "workflow_id": finding.workflow_id,
            "report_id": finding.report_id,
            "stage_key": finding.stage_key,
            "finding_title": finding.title,
            "severity": finding.severity,
            "normative_basis": finding.normative_basis,
            "xai_summary": finding.xai_json,
            "comment": comment,
            "replacement_document_id": replacement_document.id if replacement_document else None,
            "replacement_file_name": replacement_document.file_name if replacement_document else None,
        },
    )
    db.flush()
    workflow = db.scalar(select(ExpertiseWorkflow).where(ExpertiseWorkflow.id == finding.workflow_id))
    if workflow is None:
        raise ValueError("Workflow not found")
    recalculate_workflow_metrics(db, workflow)
    db.flush()
    if not _stage_has_unresolved_actions(db, workflow, finding.stage_key):
        _advance_workflow_until_blocked_or_complete(db, workflow)
        recalculate_workflow_metrics(db, workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def record_replacement_started(
    db: Session,
    finding: ExpertiseFinding,
    *,
    user_id: str | None,
    replacement_document: Document,
    comment: str | None = None,
) -> ExpertiseWorkflow:
    finding.status = "replacement_processing"
    finding.user_decision_status = "replacement_processing"
    finding.replacement_document_id = replacement_document.id
    finding.replacement_file_name = replacement_document.file_name
    finding.replacement_progress = 35
    decision = ExpertiseUserDecision(
        organization_id=finding.organization_id,
        workflow_id=finding.workflow_id,
        finding_id=finding.id,
        user_id=user_id,
        decision_type="replacement",
        comment=comment,
        replacement_document_id=replacement_document.id,
        replacement_file_name=replacement_document.file_name,
        replacement_progress=35,
        payload_json={
            "source": "backend_replacement_recheck",
            "decision_status": "replacement_processing",
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(finding)
    db.add(decision)
    log_action(
        db,
        action="estimate_expertise_replacement_started",
        entity_type="expertise_finding",
        entity_id=finding.id,
        organization_id=finding.organization_id,
        user_id=user_id,
        details={
            "workflow_id": finding.workflow_id,
            "report_id": finding.report_id,
            "stage_key": finding.stage_key,
            "finding_title": finding.title,
            "severity": finding.severity,
            "normative_basis": finding.normative_basis,
            "xai_summary": finding.xai_json,
            "comment": comment,
            "replacement_document_id": replacement_document.id,
            "replacement_file_name": replacement_document.file_name,
            "replacement_progress": 35,
        },
    )
    db.flush()
    workflow = db.scalar(select(ExpertiseWorkflow).where(ExpertiseWorkflow.id == finding.workflow_id))
    if workflow is None:
        raise ValueError("Workflow not found")
    recalculate_workflow_metrics(db, workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def complete_replacement_recheck(
    db: Session,
    *,
    finding_id: str,
    replacement_document_id: str,
    user_id: str | None,
    comment: str | None = None,
) -> ExpertiseWorkflow:
    finding = db.scalar(select(ExpertiseFinding).where(ExpertiseFinding.id == finding_id))
    if finding is None:
        raise ValueError("Expertise finding not found")
    replacement_document = db.scalar(select(Document).where(Document.id == replacement_document_id))
    if replacement_document is None:
        raise ValueError("Replacement document not found")
    report = db.scalar(select(Report).where(Report.id == finding.report_id))
    if report is not None:
        selected_ids = list(report.selected_document_ids or [])
        if replacement_document.id not in selected_ids:
            report.selected_document_ids = [*selected_ids, replacement_document.id]
            db.add(report)
            db.flush()

    stage_key = finding.stage_key
    original_title = finding.title
    workflow = record_finding_decision(
        db,
        finding,
        user_id=user_id,
        decision_type="replacement",
        comment=comment,
        replacement_document=replacement_document,
    )
    latest_decision = db.scalar(
        select(ExpertiseUserDecision)
        .where(ExpertiseUserDecision.finding_id == finding.id)
        .order_by(ExpertiseUserDecision.created_at.desc())
        .limit(1)
    )
    if latest_decision is not None:
        latest_decision.payload_json = {
            **(latest_decision.payload_json or {}),
            "source": "backend_replacement_recheck",
            "replacement_document_status": getattr(replacement_document.status, "value", str(replacement_document.status)),
            "replacement_processed_at": replacement_document.processed_at.isoformat() if replacement_document.processed_at else None,
            "replacement_stage_reached": finding.stage_key,
        }
        db.add(latest_decision)
        db.commit()
        db.refresh(workflow)
    if report is not None:
        _append_replacement_stage_findings(
            db,
            workflow=workflow,
            report=report,
            replacement_document=replacement_document,
            stage_key=stage_key,
            original_title=original_title,
        )
        recalculate_workflow_metrics(db, workflow)
        db.commit()
        db.refresh(workflow)
    return workflow


def _append_replacement_stage_findings(
    db: Session,
    *,
    workflow: ExpertiseWorkflow,
    report: Report,
    replacement_document: Document,
    stage_key: str,
    original_title: str,
) -> None:
    profile = _rules_profile_for_report(report)
    if stage_key == "filename_content":
        seeds = _build_filename_findings([replacement_document], profile=profile)
    elif stage_key == "section_content":
        seeds = _build_pp87_section_content_findings([replacement_document], profile=profile)
    elif stage_key == "quality_spell_signature":
        seeds = _build_quality_findings([replacement_document], profile=profile)
    elif stage_key == "completeness":
        documents = _load_workflow_documents(db, report)
        seeds = [seed for seed in _build_completeness_findings(documents, profile=profile) if seed["title"] == original_title]
    else:
        seeds = []

    if not seeds:
        return

    stage = _get_stage(db, workflow, stage_key)
    for seed in seeds:
        db.add(
            ExpertiseFinding(
                organization_id=workflow.organization_id,
                report_id=workflow.report_id,
                workflow_id=workflow.id,
                stage_id=stage.id,
                document_id=seed["document_id"],
                stage_key=seed["stage_key"],
                title=f"После замены: {seed['title']}",
                description=seed["description"],
                severity=seed["severity"],
                confidence_score=seed["confidence_score"],
                normative_basis=seed["normative_basis"],
                source_ref=seed["source_ref"],
                recommendation=seed["recommendation"],
                xai_json=[
                    "Вывод создан при backend re-check replacement-файла.",
                    f"Replacement document: {replacement_document.file_name}.",
                    *seed["xai_json"],
                ],
                status="open",
                replacement_progress=0,
            )
        )
    db.flush()


def serialize_workflow(db: Session, workflow: ExpertiseWorkflow) -> dict:
    stages = list(
        db.scalars(
            select(ExpertiseWorkflowStage)
            .where(ExpertiseWorkflowStage.workflow_id == workflow.id)
            .order_by(ExpertiseWorkflowStage.order_number)
        )
    )
    findings = list(
        db.scalars(
            select(ExpertiseFinding)
            .where(ExpertiseFinding.workflow_id == workflow.id)
            .order_by(ExpertiseFinding.created_at)
        )
    )
    decisions = list(
        db.scalars(
            select(ExpertiseUserDecision)
            .where(ExpertiseUserDecision.workflow_id == workflow.id)
            .order_by(ExpertiseUserDecision.created_at)
        )
    )
    latest_decision_by_finding = {decision.finding_id: decision for decision in decisions}
    document_ids = {finding.document_id for finding in findings if finding.document_id}
    replacement_document_ids = {finding.replacement_document_id for finding in findings if finding.replacement_document_id}
    document_index = {
        document.id: document
        for document in db.scalars(select(Document).where(Document.id.in_(document_ids | replacement_document_ids)))
    } if document_ids or replacement_document_ids else {}
    findings_by_stage: dict[str, list[dict]] = {stage.stage_key: [] for stage in stages}

    for finding in findings:
        document = document_index.get(finding.document_id or "")
        decision = latest_decision_by_finding.get(finding.id)
        serialized_decision = None
        if decision is not None:
            decision_status = finding.user_decision_status or decision.payload_json.get("decision_status") or decision.decision_type
            serialized_decision = {
                "status": decision_status,
                "label": _decision_label(decision_status),
                "updated_at": decision.created_at,
                "replacement_file_name": decision.replacement_file_name,
                "replacement_progress": decision.replacement_progress,
                "decision_type": decision.decision_type,
                "comment": decision.comment,
            }
        serialized = {
            "id": finding.id,
            "created_at": finding.created_at,
            "updated_at": finding.updated_at,
            "stage_id": finding.stage_id,
            "stage_key": finding.stage_key,
            "stage_title": next((stage.short_title for stage in stages if stage.stage_key == finding.stage_key), finding.stage_key),
            "document_id": finding.document_id,
            "document_name": document.file_name if document is not None else "Пакет документов",
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "confidence_score": finding.confidence_score,
            "normative_basis": finding.normative_basis,
            "source_ref": finding.source_ref,
            "recommendation": finding.recommendation,
            "xai_summary": finding.xai_json,
            "status": finding.status,
            "decision": serialized_decision,
        }
        findings_by_stage.setdefault(finding.stage_key, []).append(serialized)

    return {
        "id": workflow.id,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "organization_id": workflow.organization_id,
        "report_id": workflow.report_id,
        "status": workflow.status,
        "progress": workflow.progress,
        "eta_seconds": workflow.eta_seconds,
        "checked_files": workflow.checked_files,
        "total_files": workflow.total_files,
        "unresolved_findings": workflow.unresolved_findings,
        "current_stage_key": workflow.current_stage_key,
        "model_version": workflow.model_version,
        "rule_version": workflow.rule_version,
        "stages": [
            {
                "id": stage.id,
                "created_at": stage.created_at,
                "updated_at": stage.updated_at,
                "stage_key": stage.stage_key,
                "title": stage.title,
                "short_title": stage.short_title,
                "order_number": stage.order_number,
                "status": stage.status,
                "progress": stage.progress,
                "checked_files": stage.checked_files,
                "total_files": stage.total_files,
                "findings_count": len(findings_by_stage.get(stage.stage_key, [])),
                "findings": findings_by_stage.get(stage.stage_key, []),
            }
            for stage in stages
        ],
    }


def _decision_label(status: str) -> str:
    return {
        "approved": "Пользователь подтвердил, что вывод допустим для дальнейшей проверки.",
        "skipped": "Пользователь исключил этот файл или пункт из дальнейшей проверки.",
        "replacement_processing": "Новый файл проходит pipeline до текущего этапа проверки.",
        "replacement_resolved": "Замена прошла демонстрационный pipeline до текущего этапа.",
    }.get(status, "Решение пользователя сохранено.")
