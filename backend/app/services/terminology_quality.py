from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TerminologyRule:
    key: str
    issue_type: str
    pattern: re.Pattern[str]
    suggestion: str
    explanation: str
    confidence: float


@dataclass(frozen=True)
class TerminologyIssue:
    key: str
    issue_type: str
    matched_text: str
    suggestion: str
    explanation: str
    confidence: float
    evidence: str


DOMAIN_TERMS = (
    "сметная",
    "сметный",
    "сметная стоимость",
    "сводный сметный расчет",
    "локальный сметный расчет",
    "объектный сметный расчет",
    "ведомость объемов работ",
    "коммерческое предложение",
    "проектная документация",
    "государственная экспертиза",
)

ALLOWED_ABBREVIATIONS = {
    "лср",
    "оср",
    "сср",
    "вор",
    "гип",
    "сро",
    "мп",
    "м.п",
    "пд",
    "рии",
}

TERMINOLOGY_RULES = (
    TerminologyRule(
        key="typo_estimate_double_n",
        issue_type="spelling",
        pattern=re.compile(r"\bсметнн\w*\b", flags=re.IGNORECASE),
        suggestion="сметная / сметный",
        explanation="В проектно-сметной документации используется корень `сметн-` без удвоенной `н`.",
        confidence=0.86,
    ),
    TerminologyRule(
        key="typo_cost",
        issue_type="spelling",
        pattern=re.compile(r"\bстоим(?:о)?т[ьт]\b|\bстоимостть\b", flags=re.IGNORECASE),
        suggestion="стоимость",
        explanation="Слово `стоимость` найдено в искаженной форме.",
        confidence=0.88,
    ),
    TerminologyRule(
        key="typo_calculation_double_s",
        issue_type="spelling",
        pattern=re.compile(r"\bрассчет\w*\b", flags=re.IGNORECASE),
        suggestion="расчет / расчеты",
        explanation="В деловой и сметной терминологии используется форма `расчет`, не `рассчет`.",
        confidence=0.84,
    ),
    TerminologyRule(
        key="typo_document",
        issue_type="spelling",
        pattern=re.compile(r"\bдокуменнт\w*\b", flags=re.IGNORECASE),
        suggestion="документ",
        explanation="Найдено техническое или орфографическое искажение слова `документ`.",
        confidence=0.82,
    ),
    TerminologyRule(
        key="typo_application",
        issue_type="spelling",
        pattern=re.compile(r"\bзаявленние\w*\b", flags=re.IGNORECASE),
        suggestion="заявление",
        explanation="Найдено искажение базового термина подачи документов.",
        confidence=0.82,
    ),
    TerminologyRule(
        key="typo_object_sign",
        issue_type="spelling",
        pattern=re.compile(r"\bобьект\w*\b", flags=re.IGNORECASE),
        suggestion="объект / объектный",
        explanation="В нормативной и проектной терминологии используется `объект` через твердый знак.",
        confidence=0.86,
    ),
    TerminologyRule(
        key="typo_statement",
        issue_type="spelling",
        pattern=re.compile(r"\bведомаст\w*\b", flags=re.IGNORECASE),
        suggestion="ведомость",
        explanation="Для ведомостей объемов работ используется термин `ведомость`.",
        confidence=0.82,
    ),
    TerminologyRule(
        key="typo_commercial",
        issue_type="spelling",
        pattern=re.compile(r"\bкомерческ\w*\b", flags=re.IGNORECASE),
        suggestion="коммерческий / коммерческое предложение",
        explanation="В слове `коммерческий` используется удвоенная `м`.",
        confidence=0.82,
    ),
    TerminologyRule(
        key="wrong_estimate_adjective",
        issue_type="terminology",
        pattern=re.compile(r"\bсметов(?:ая|ое|ый|ые|ого|ому|ыми|ых|ом|ую|ой)\b", flags=re.IGNORECASE),
        suggestion="сметная / сметный",
        explanation="Для расчетов и документации корректен термин `сметный`, а не `сметовый`.",
        confidence=0.78,
    ),
)

LATIN_TO_CYRILLIC = str.maketrans(
    {
        "a": "а",
        "c": "с",
        "e": "е",
        "o": "о",
        "p": "р",
        "x": "х",
        "y": "у",
        "k": "к",
        "m": "м",
        "t": "т",
        "h": "н",
        "b": "в",
        "A": "А",
        "C": "С",
        "E": "Е",
        "O": "О",
        "P": "Р",
        "X": "Х",
        "Y": "У",
        "K": "К",
        "M": "М",
        "T": "Т",
        "H": "Н",
        "B": "В",
    }
)


def assess_terminology_quality(text: str, *, limit: int = 8) -> list[TerminologyIssue]:
    issues: list[TerminologyIssue] = []
    for rule in TERMINOLOGY_RULES:
        for match in rule.pattern.finditer(text):
            matched_text = match.group(0)
            issues.append(
                TerminologyIssue(
                    key=rule.key,
                    issue_type=rule.issue_type,
                    matched_text=matched_text,
                    suggestion=rule.suggestion,
                    explanation=rule.explanation,
                    confidence=rule.confidence,
                    evidence=_snippet(text, match.start(), match.end()),
                )
            )
            if len(issues) >= limit:
                return issues

    for issue in _detect_ocr_mixed_script_terms(text):
        if all(existing.matched_text.lower() != issue.matched_text.lower() for existing in issues):
            issues.append(issue)
            if len(issues) >= limit:
                return issues
    return issues


def describe_terminology_quality_rules() -> dict[str, object]:
    return {
        "provider": "local-terminology-rules-v1",
        "mode": "rules",
        "runtime_scope": "local_server",
        "sends_documents_to_external_services": False,
        "domain": "state_expertise_estimate_cost",
        "rule_count": len(TERMINOLOGY_RULES),
        "domain_terms": list(DOMAIN_TERMS),
        "allowed_abbreviations": sorted(ALLOWED_ABBREVIATIONS),
        "checks": ["spelling", "terminology", "ocr_mixed_script_noise"],
    }


def _detect_ocr_mixed_script_terms(text: str) -> list[TerminologyIssue]:
    issues: list[TerminologyIssue] = []
    for match in re.finditer(r"\b[0-9A-Za-zА-Яа-яЁё.\-]{4,}\b", text):
        word = match.group(0)
        lowered_word = word.lower().strip(".")
        if lowered_word in ALLOWED_ABBREVIATIONS:
            continue
        has_latin = any("a" <= char.lower() <= "z" for char in word)
        has_cyrillic = any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in word)
        if not has_latin or not has_cyrillic:
            continue
        normalized = word.translate(LATIN_TO_CYRILLIC).lower()
        if not _looks_like_domain_term(normalized):
            continue
        issues.append(
            TerminologyIssue(
                key="ocr_mixed_script_domain_term",
                issue_type="ocr_noise",
                matched_text=word,
                suggestion=normalized,
                explanation=(
                    "Слово похоже на проектно-сметный термин, но часть букв распознана латиницей. "
                    "Это типичный OCR-noise для сканов."
                ),
                confidence=0.72,
                evidence=_snippet(text, match.start(), match.end()),
            )
        )
    return issues


def _looks_like_domain_term(normalized_word: str) -> bool:
    compact_terms = {
        "смет",
        "стоим",
        "расчет",
        "проект",
        "ведом",
        "коммерч",
        "документ",
        "экспертиз",
        "объект",
    }
    return any(marker in normalized_word for marker in compact_terms)


def _snippet(text: str, start: int, end: int, *, window: int = 70) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""

    prefix_text = text[:start]
    normalized_start = len(" ".join(prefix_text.split()))
    normalized_end = normalized_start + len(text[start:end].strip())
    snippet_start = max(0, normalized_start - window)
    snippet_end = min(len(normalized), normalized_end + window)
    prefix = "..." if snippet_start > 0 else ""
    suffix = "..." if snippet_end < len(normalized) else ""
    return f"{prefix}{normalized[snippet_start:snippet_end]}{suffix}"
