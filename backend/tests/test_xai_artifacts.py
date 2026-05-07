from __future__ import annotations

from dataclasses import dataclass

from app.models import RequirementStatus, RiskLevel
from app.services.xai import build_requirement_artifacts


@dataclass
class FragmentStub:
    id: str
    document_id: str
    fragment_text: str


def test_build_requirement_artifacts_returns_richer_payload():
    artifacts = build_requirement_artifacts(
        requirement_title="Публикация сведений о лицензии",
        requirement_text="Организация должна разместить сведения о лицензии на официальном сайте.",
        category="Официальный сайт",
        applicability_reason="Требование относится к образовательному сценарию.",
        requirement_status=RequirementStatus.data_found,
        confidence=0.87,
        risk_level=RiskLevel.low,
        source_documents_count=1,
        required_data=["лицензии", "официальном", "сайте"],
        ranked_evidence=[
            (
                FragmentStub(
                    id="fragment-1",
                    document_id="document-1",
                    fragment_text="Лицензия на образовательную деятельность размещена на официальном сайте организации.",
                ),
                0.91,
            )
        ],
    )

    assert artifacts.found_data
    assert "score: 0.91" in artifacts.found_data[0]
    assert artifacts.evidence_payload[0]["matched_keywords"]
    assert "Уровень риска: low" in artifacts.conclusion
    assert any("Наиболее релевантное подтверждение" in item for item in artifacts.logic_json)
    assert "Лучшее подтверждение" in artifacts.explanation_text
    assert artifacts.recommended_action
