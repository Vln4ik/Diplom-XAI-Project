import type { EstimateExpertiseDecision, EstimateExpertiseFinding } from "./estimateExpertise";
import type { DocumentItem, ReportItem, RequirementItem, RiskItem } from "./types";

const CLOSED_REQUIREMENT_STATUSES = new Set(["confirmed", "rejected", "included_in_report", "archived", "not_applicable"]);
const ACTIVE_DOCUMENT_STATUSES = new Set(["queued", "processing", "requires_review", "failed", "outdated"]);
const CLOSED_RISK_STATUSES = new Set(["resolved", "accepted", "closed", "archived"]);
const FULLY_FORMED_REPORT_STATUSES = new Set(["awaiting_approval", "approved", "exported", "archived"]);

export function isActiveRequirement(requirement: RequirementItem): boolean {
  return !CLOSED_REQUIREMENT_STATUSES.has(requirement.status);
}

export function isActiveDocumentRequirement(document: DocumentItem): boolean {
  return ACTIVE_DOCUMENT_STATUSES.has(document.status);
}

export function isActiveRiskRequirement(risk: RiskItem): boolean {
  return !CLOSED_RISK_STATUSES.has(risk.status);
}

export function isReportFullyFormed(report: ReportItem): boolean {
  return report.readiness_percent >= 100 || FULLY_FORMED_REPORT_STATUSES.has(report.status);
}

export function isEstimateDecisionResolved(decision?: EstimateExpertiseDecision | null): boolean {
  return Boolean(decision && decision.status !== "replacement_processing");
}

export function isActiveEstimateFinding(finding: EstimateExpertiseFinding): boolean {
  if (finding.severity === "info") {
    return false;
  }
  if (isEstimateDecisionResolved(finding.decision)) {
    return false;
  }
  return !["approved", "skipped", "replacement_resolved", "resolved", "closed"].includes(finding.status ?? "");
}

export function countActiveBaseAiRequirements(params: {
  documents: DocumentItem[];
  requirements: RequirementItem[];
  risks: RiskItem[];
}): number {
  return (
    params.documents.filter(isActiveDocumentRequirement).length +
    params.requirements.filter(isActiveRequirement).length +
    params.risks.filter(isActiveRiskRequirement).length
  );
}
