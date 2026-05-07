import { clearSession, getAccessToken, setAccessToken } from "./session";
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
  website?: string;
  email?: string;
  phone?: string;
}): Promise<Organization> {
  return request<Organization>("/api/organizations", {
    method: "POST",
    body: JSON.stringify({
      organization_type: "educational",
      ...payload,
    }),
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
  payload: { files: File[]; category: string; tags?: string },
): Promise<DocumentItem[]> {
  const formData = new FormData();
  for (const file of payload.files) {
    formData.append("files", file);
  }
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
