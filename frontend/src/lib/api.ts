import { clearSession, getAccessToken, setAccessToken } from "./session";
import type {
  EstimateExpertiseDecision,
  EstimateExpertiseFinding,
  EstimateExpertiseStage,
  EstimateExpertiseWorkflow,
  ExpertiseFindingSeverity,
  ExpertiseStageStatus,
} from "./estimateExpertise";
import type {
  AuditLogItem,
  Dashboard,
  DocumentSearchMatch,
  DocumentItem,
  Explanation,
  MemberItem,
  ExportFile,
  NotificationItem,
  Organization,
  OrganizationAutofillSuggestion,
  ReportItem,
  ReportMatrixRow,
  ReportSection,
  ReportVersion,
  RequirementItem,
  RiskItem,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function downloadAuthorizedFile(path: string, fileName: string): Promise<void> {
  const token = getAccessToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Download failed: ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string): Promise<void> {
  const data = await request<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(data.access_token);
}

export function logout(): void {
  clearSession();
}

export function fetchOrganizations(): Promise<Organization[]> {
  return request<Organization[]>("/api/organizations");
}

export function createOrganization(payload: {
  name: string;
  short_name?: string;
  inn?: string;
  kpp?: string;
  ogrn?: string;
  legal_address?: string;
  actual_address?: string;
  organization_type?: string;
  okved?: string;
  website?: string;
  email?: string;
  phone?: string;
  director_name?: string;
  responsible_person?: string;
}): Promise<Organization> {
  return request<Organization>("/api/organizations", {
    method: "POST",
    body: JSON.stringify({
      organization_type: "educational",
      ...payload,
    }),
  });
}

export function updateOrganization(
  organizationId: string,
  payload: {
    name?: string;
    short_name?: string;
    inn?: string;
    kpp?: string;
    ogrn?: string;
    legal_address?: string;
    actual_address?: string;
    organization_type?: string;
    okved?: string;
    website?: string;
    email?: string;
    phone?: string;
    director_name?: string;
    responsible_person?: string;
  },
): Promise<Organization> {
  return request<Organization>(`/api/organizations/${organizationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteOrganization(organizationId: string): Promise<Organization> {
  return request<Organization>(`/api/organizations/${organizationId}`, {
    method: "DELETE",
  });
}

export function autofillOrganizationFromDocuments(organizationId: string): Promise<OrganizationAutofillSuggestion> {
  return request<OrganizationAutofillSuggestion>(`/api/organizations/${organizationId}/autofill`, {
    method: "POST",
  });
}

export function fetchMembers(organizationId: string): Promise<MemberItem[]> {
  return request<MemberItem[]>(`/api/organizations/${organizationId}/members`);
}

export function fetchDashboard(organizationId: string): Promise<Dashboard> {
  return request<Dashboard>(`/api/organizations/${organizationId}/dashboard`);
}

export function fetchNotifications(organizationId: string, onlyUnread = false): Promise<NotificationItem[]> {
  const params = new URLSearchParams();
  if (onlyUnread) {
    params.set("only_unread", "true");
  }
  return request<NotificationItem[]>(
    `/api/organizations/${organizationId}/notifications${params.size ? `?${params.toString()}` : ""}`,
  );
}

export function markNotificationRead(notificationId: string): Promise<NotificationItem> {
  return request<NotificationItem>(`/api/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export function markAllNotificationsRead(organizationId: string): Promise<{ updated: number }> {
  return request<{ updated: number }>(`/api/organizations/${organizationId}/notifications/read-all`, {
    method: "POST",
  });
}

export function fetchAuditLogs(organizationId: string): Promise<AuditLogItem[]> {
  return request<AuditLogItem[]>(`/api/organizations/${organizationId}/audit-logs`);
}

export function fetchDocuments(organizationId: string): Promise<DocumentItem[]> {
  return request<DocumentItem[]>(`/api/organizations/${organizationId}/documents`);
}

export function uploadDocuments(
  organizationId: string,
  payload: { files: File[]; category: string; tags?: string; relativePaths?: string[] },
): Promise<DocumentItem[]> {
  const formData = new FormData();
  payload.files.forEach((file, index) => {
    formData.append("files", file);
    formData.append("relative_paths", payload.relativePaths?.[index] || file.name);
  });
  formData.append("category", payload.category);
  if (payload.tags) {
    formData.append("tags", payload.tags);
  }
  return request<DocumentItem[]>(`/api/organizations/${organizationId}/documents`, {
    method: "POST",
    body: formData,
  });
}

export function processDocument(documentId: string): Promise<{ document_id: string; status: string; task_id?: string | null }> {
  return request(`/api/documents/${documentId}/process`, {
    method: "POST",
  });
}

export function deleteDocument(documentId: string): Promise<DocumentItem> {
  return request<DocumentItem>(`/api/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function searchDocuments(
  organizationId: string,
  payload: { query: string; category?: string; status?: string; tag?: string },
): Promise<DocumentSearchMatch[]> {
  const params = new URLSearchParams();
  params.set("query", payload.query);
  if (payload.category) {
    params.set("category", payload.category);
  }
  if (payload.status) {
    params.set("status", payload.status);
  }
  if (payload.tag) {
    params.set("tag", payload.tag);
  }
  return request<DocumentSearchMatch[]>(`/api/organizations/${organizationId}/documents/search?${params.toString()}`);
}

export function fetchReports(organizationId: string): Promise<ReportItem[]> {
  return request<ReportItem[]>(`/api/organizations/${organizationId}/reports`);
}

export function createReport(
  organizationId: string,
  payload: {
    title: string;
    report_type?: string;
    comment?: string;
    selected_document_ids?: string[];
  },
): Promise<ReportItem> {
  return request<ReportItem>(`/api/organizations/${organizationId}/reports`, {
    method: "POST",
    body: JSON.stringify({
      report_type: "readiness_report",
      ...payload,
    }),
  });
}

export function deleteReport(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}`, {
    method: "DELETE",
  });
}

export function analyzeReport(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}/analyze`, {
    method: "POST",
  });
}

export function generateReport(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}/generate`, {
    method: "POST",
  });
}

type RawEstimateExpertiseDecision = {
  status: string;
  label: string;
  updated_at: string;
  replacement_file_name?: string | null;
  replacement_progress?: number;
  decision_type?: string;
  comment?: string | null;
};

type RawEstimateExpertiseFinding = {
  id: string;
  stage_id?: string | null;
  stage_key: string;
  stage_title: string;
  document_id?: string | null;
  document_name: string;
  title: string;
  description: string;
  severity: string;
  confidence_score: number;
  normative_basis: string;
  source_ref: string;
  recommendation: string;
  xai_summary: string[];
  status: string;
  decision?: RawEstimateExpertiseDecision | null;
};

type RawEstimateExpertiseStage = {
  id: string;
  stage_key: string;
  title: string;
  short_title: string;
  order_number: number;
  status: string;
  progress: number;
  checked_files: number;
  total_files: number;
  findings_count: number;
  findings: RawEstimateExpertiseFinding[];
};

type RawEstimateExpertiseWorkflow = {
  id: string;
  status: string;
  progress: number;
  eta_seconds: number;
  checked_files: number;
  total_files: number;
  unresolved_findings: number;
  stages: RawEstimateExpertiseStage[];
};

function formatEstimateEta(etaSeconds: number): string {
  const minutes = Math.max(1, Math.round(etaSeconds / 60));
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours === 0) {
    return `${restMinutes} мин`;
  }
  return `${hours} ч ${restMinutes.toString().padStart(2, "0")} мин`;
}

function normalizeEstimateDecision(raw: RawEstimateExpertiseDecision): EstimateExpertiseDecision {
  return {
    status: raw.status as EstimateExpertiseDecision["status"],
    label: raw.label,
    updatedAt: raw.updated_at,
    replacementFileName: raw.replacement_file_name ?? undefined,
    replacementProgress: raw.replacement_progress,
    decisionType: raw.decision_type,
    comment: raw.comment,
  };
}

function normalizeEstimateFinding(raw: RawEstimateExpertiseFinding): EstimateExpertiseFinding {
  return {
    id: raw.id,
    stageId: raw.stage_id ?? raw.stage_key,
    stageTitle: raw.stage_title,
    documentName: raw.document_name,
    title: raw.title,
    description: raw.description,
    severity: raw.severity as ExpertiseFindingSeverity,
    confidence: raw.confidence_score,
    normativeBasis: raw.normative_basis,
    sourceRef: raw.source_ref,
    recommendation: raw.recommendation,
    xaiSummary: raw.xai_summary,
    status: raw.status,
    decision: raw.decision ? normalizeEstimateDecision(raw.decision) : null,
  };
}

function normalizeEstimateWorkflow(raw: RawEstimateExpertiseWorkflow): EstimateExpertiseWorkflow {
  const stages: EstimateExpertiseStage[] = raw.stages.map((stage) => ({
    id: stage.stage_key,
    order: stage.order_number,
    title: stage.title,
    shortTitle: stage.short_title,
    status: stage.status as ExpertiseStageStatus,
    progress: Math.round(stage.progress),
    checkedFiles: stage.checked_files,
    totalFiles: stage.total_files,
    findings: stage.findings.map(normalizeEstimateFinding),
  }));
  return {
    status: raw.status,
    progress: Math.round(raw.progress),
    etaLabel: formatEstimateEta(raw.eta_seconds),
    checkedFiles: raw.checked_files,
    totalFiles: raw.total_files,
    unresolvedFindings: raw.unresolved_findings,
    documents: [],
    stages,
  };
}

export async function startEstimateExpertiseWorkflow(reportId: string): Promise<EstimateExpertiseWorkflow> {
  const raw = await request<RawEstimateExpertiseWorkflow>(`/api/reports/${reportId}/estimate-expertise/start`, {
    method: "POST",
  });
  return normalizeEstimateWorkflow(raw);
}

export async function fetchEstimateExpertiseWorkflow(reportId: string): Promise<EstimateExpertiseWorkflow> {
  const raw = await request<RawEstimateExpertiseWorkflow>(`/api/reports/${reportId}/estimate-expertise/state`);
  return normalizeEstimateWorkflow(raw);
}

export async function approveEstimateExpertiseFinding(findingId: string): Promise<EstimateExpertiseWorkflow> {
  const raw = await request<RawEstimateExpertiseWorkflow>(`/api/estimate-expertise/findings/${findingId}/approve`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return normalizeEstimateWorkflow(raw);
}

export async function skipEstimateExpertiseFinding(findingId: string): Promise<EstimateExpertiseWorkflow> {
  const raw = await request<RawEstimateExpertiseWorkflow>(`/api/estimate-expertise/findings/${findingId}/skip`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return normalizeEstimateWorkflow(raw);
}

export async function uploadEstimateExpertiseReplacement(findingId: string, file: File): Promise<EstimateExpertiseWorkflow> {
  const formData = new FormData();
  formData.append("file", file);
  const raw = await request<RawEstimateExpertiseWorkflow>(`/api/estimate-expertise/findings/${findingId}/replacement`, {
    method: "POST",
    body: formData,
  });
  return normalizeEstimateWorkflow(raw);
}

export function submitReportForApproval(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}/submit-for-approval`, {
    method: "POST",
  });
}

export function approveReport(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}/approve`, {
    method: "POST",
  });
}

export function returnReportToRevision(reportId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/reports/${reportId}/return-to-revision`, {
    method: "POST",
  });
}

export async function exportReport(
  reportId: string,
  exportType: "docx" | "matrix" | "package" | "explanations",
): Promise<void> {
  const exportMeta = await request<ExportFile>(`/api/reports/${reportId}/export/${exportType}`, {
    method: "POST",
  });
  await downloadAuthorizedFile(`/api/exports/${exportMeta.id}/download`, exportMeta.file_name);
}

export function fetchRequirements(organizationId: string): Promise<RequirementItem[]> {
  return request<RequirementItem[]>(`/api/organizations/${organizationId}/requirements`);
}

export function updateRequirement(
  requirementId: string,
  payload: {
    title?: string;
    category?: string;
    text?: string;
    applicability_status?: string;
    applicability_reason?: string;
    user_comment?: string;
    status?: string;
  },
): Promise<RequirementItem> {
  return request<RequirementItem>(`/api/requirements/${requirementId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function bulkUpdateRequirements(
  organizationId: string,
  payload: {
    requirement_ids: string[];
    status?: string;
    applicability_status?: string;
    user_comment?: string;
  },
): Promise<RequirementItem[]> {
  return request<RequirementItem[]>(`/api/organizations/${organizationId}/requirements/bulk-update`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refreshRequirementArtifacts(requirementId: string): Promise<RequirementItem> {
  return request<RequirementItem>(`/api/requirements/${requirementId}/refresh-artifacts`, {
    method: "POST",
  });
}

export function confirmRequirement(requirementId: string): Promise<RequirementItem> {
  return request<RequirementItem>(`/api/requirements/${requirementId}/confirm`, {
    method: "POST",
  });
}

export function rejectRequirement(requirementId: string): Promise<RequirementItem> {
  return request<RequirementItem>(`/api/requirements/${requirementId}/reject`, {
    method: "POST",
  });
}

export function fetchRisks(organizationId: string): Promise<RiskItem[]> {
  return request<RiskItem[]>(`/api/organizations/${organizationId}/risks`);
}

export function updateRisk(
  riskId: string,
  payload: { assigned_to_id?: string | null; status?: string; recommended_action?: string; description?: string },
): Promise<RiskItem> {
  return request<RiskItem>(`/api/risks/${riskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function resolveRisk(riskId: string): Promise<RiskItem> {
  return request<RiskItem>(`/api/risks/${riskId}/resolve`, {
    method: "POST",
  });
}

export function fetchSections(reportId: string): Promise<ReportSection[]> {
  return request<ReportSection[]>(`/api/reports/${reportId}/sections`);
}

export function fetchReportVersions(reportId: string): Promise<ReportVersion[]> {
  return request<ReportVersion[]>(`/api/reports/${reportId}/versions`);
}

export function restoreReportVersion(versionId: string): Promise<ReportItem> {
  return request<ReportItem>(`/api/report-versions/${versionId}/restore`, {
    method: "POST",
  });
}

export function updateSection(
  reportId: string,
  sectionId: string,
  payload: { title?: string; content?: string; status?: string },
): Promise<ReportSection> {
  return request<ReportSection>(`/api/reports/${reportId}/sections/${sectionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function fetchMatrix(reportId: string): Promise<ReportMatrixRow[]> {
  return request<ReportMatrixRow[]>(`/api/reports/${reportId}/matrix`);
}

export function fetchExplanation(requirementId: string): Promise<Explanation> {
  return request<Explanation>(`/api/requirements/${requirementId}/explanation`);
}
