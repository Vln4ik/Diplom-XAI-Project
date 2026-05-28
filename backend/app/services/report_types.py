from __future__ import annotations

READINESS_REPORT = "readiness_report"
TEMPLATE_REPORT = "template_report"
DOCUMENT_COMPLETENESS_REPORT = "document_completeness"
STATE_EXPERTISE_ESTIMATE_COST_REPORT = "state_expertise_estimate_cost_verification"
STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT = "state_expertise_estimate_cost_verification_pp87"

SUPPORTED_REPORT_TYPES = {
    READINESS_REPORT,
    TEMPLATE_REPORT,
    DOCUMENT_COMPLETENESS_REPORT,
    STATE_EXPERTISE_ESTIMATE_COST_REPORT,
    STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT,
}

SPECIAL_WORKFLOW_REPORT_TYPES = {
    STATE_EXPERTISE_ESTIMATE_COST_REPORT,
    STATE_EXPERTISE_ESTIMATE_COST_PP87_REPORT,
}


def validate_report_type(value: str) -> str:
    if value not in SUPPORTED_REPORT_TYPES:
        supported = ", ".join(sorted(SUPPORTED_REPORT_TYPES))
        raise ValueError(f"Unsupported report_type '{value}'. Supported values: {supported}")
    return value


def requires_special_workflow(report_type: str) -> bool:
    return report_type in SPECIAL_WORKFLOW_REPORT_TYPES
