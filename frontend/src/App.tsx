import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import {
  approveReport,
  analyzeReport,
  bulkUpdateRequirements,
  confirmRequirement,
  createOrganization,
  createReport,
  exportReport,
  fetchAuditLogs,
  fetchDashboard,
  fetchDocuments,
  fetchExplanation,
  fetchMembers,
  fetchMatrix,
  fetchNotifications,
  fetchOrganizations,
  fetchReportVersions,
  fetchReports,
  fetchRequirements,
  refreshRequirementArtifacts,
  fetchRisks,
  fetchSections,
  generateReport,
  markAllNotificationsRead,
  markNotificationRead,
  processDocument,
  rejectRequirement,
  resolveRisk,
  restoreReportVersion,
  returnReportToRevision,
  submitReportForApproval,
  searchDocuments,
  updateRequirement,
  updateRisk,
  updateSection,
  uploadDocuments,
} from "./lib/api";
import { getAccessToken } from "./lib/session";
import type {
  AuditLogItem,
  Dashboard,
  DocumentSearchMatch,
  DocumentItem,
  Explanation,
  MemberItem,
  NotificationItem,
  Organization,
  ReportItem,
  ReportMatrixRow,
  ReportSection,
  ReportVersion,
  RequirementItem,
  RiskItem,
} from "./lib/types";
import { AuditLogPage } from "./pages/AuditLogPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { ExplanationsPage } from "./pages/ExplanationsPage";
import { LoginPage } from "./pages/LoginPage";
import { MatrixPage } from "./pages/MatrixPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ReportEditorPage } from "./pages/ReportEditorPage";
import { ReportsPage } from "./pages/ReportsPage";
import { RequirementsPage } from "./pages/RequirementsPage";
import { RisksPage } from "./pages/RisksPage";

function AppShell() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [documentSearchResults, setDocumentSearchResults] = useState<DocumentSearchMatch[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [reportVersions, setReportVersions] = useState<ReportVersion[]>([]);
  const [matrixRows, setMatrixRows] = useState<ReportMatrixRow[]>([]);
  const [requirements, setRequirements] = useState<RequirementItem[]>([]);
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const selectedOrganization = organizations.find((organization) => organization.id === selectedOrganizationId) ?? null;

  async function reloadReports(organizationId: string, preferredReportId?: string | null) {
    const items = await fetchReports(organizationId);
    setReports(items);
    const nextReportId = preferredReportId ?? selectedReportId ?? items[0]?.id ?? null;
    setSelectedReportId(nextReportId);
    return { items, nextReportId };
  }

  useEffect(() => {
    fetchOrganizations()
      .then((items) => {
        setOrganizations(items);
        if (!selectedOrganizationId && items.length > 0) {
          setSelectedOrganizationId(items[0].id);
        }
      })
      .catch(() => undefined);
  }, [selectedOrganizationId]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      return;
    }
    setDocumentSearchResults([]);
    fetchDashboard(selectedOrganizationId).then(setDashboard).catch(() => setDashboard(null));
    fetchDocuments(selectedOrganizationId).then(setDocuments).catch(() => setDocuments([]));
    fetchMembers(selectedOrganizationId).then(setMembers).catch(() => setMembers([]));
    fetchNotifications(selectedOrganizationId).then(setNotifications).catch(() => setNotifications([]));
    fetchAuditLogs(selectedOrganizationId).then(setAuditLogs).catch(() => setAuditLogs([]));
    reloadReports(selectedOrganizationId)
      .then(async (items) => {
        if (!items.nextReportId) {
          setSections([]);
          setMatrixRows([]);
        }
      })
      .catch(() => setReports([]));
    fetchRequirements(selectedOrganizationId)
      .then((items) => {
        setRequirements(items);
        setSelectedRequirementId((current) =>
          current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null,
        );
      })
      .catch(() => setRequirements([]));
    fetchRisks(selectedOrganizationId).then(setRisks).catch(() => setRisks([]));
  }, [selectedOrganizationId]);

  useEffect(() => {
    if (!selectedReportId) {
      setSections([]);
      setMatrixRows([]);
      setReportVersions([]);
      return;
    }
    fetchSections(selectedReportId).then(setSections).catch(() => setSections([]));
    fetchMatrix(selectedReportId).then(setMatrixRows).catch(() => setMatrixRows([]));
    fetchReportVersions(selectedReportId).then(setReportVersions).catch(() => setReportVersions([]));
  }, [selectedReportId]);

  useEffect(() => {
    if (!selectedRequirementId) {
      setExplanation(null);
      return;
    }
    fetchExplanation(selectedRequirementId).then(setExplanation).catch(() => setExplanation(null));
  }, [selectedRequirementId]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      return;
    }
    const hasActiveDocumentProcessing = documents.some((document) => ["queued", "processing"].includes(document.status));
    if (!hasActiveDocumentProcessing) {
      return;
    }

    const intervalId = window.setInterval(() => {
      fetchDocuments(selectedOrganizationId).then(setDocuments).catch(() => undefined);
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [documents, selectedOrganizationId]);

  useEffect(() => {
    if (!selectedOrganizationId) {
      return;
    }
    const hasActiveReportAnalysis = reports.some((report) => report.status === "analyzing");
    if (!hasActiveReportAnalysis) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshOrganizationState(selectedReportId);
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [reports, selectedOrganizationId, selectedReportId]);

  async function refreshOrganizationState(reportId?: string | null) {
    if (!selectedOrganizationId) {
      return;
    }
    const preferredReportId = reportId ?? selectedReportId;
    await reloadReports(selectedOrganizationId, preferredReportId);
    fetchDashboard(selectedOrganizationId).then(setDashboard).catch(() => setDashboard(null));
    fetchNotifications(selectedOrganizationId).then(setNotifications).catch(() => setNotifications([]));
    fetchAuditLogs(selectedOrganizationId).then(setAuditLogs).catch(() => setAuditLogs([]));
    fetchRequirements(selectedOrganizationId)
      .then((items) => {
        setRequirements(items);
        setSelectedRequirementId((current) =>
          current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null,
        );
      })
      .catch(() => setRequirements([]));
    fetchRisks(selectedOrganizationId).then(setRisks).catch(() => setRisks([]));
    if (selectedRequirementId) {
      fetchExplanation(selectedRequirementId).then(setExplanation).catch(() => setExplanation(null));
    }
    if (preferredReportId) {
      fetchSections(preferredReportId).then(setSections).catch(() => setSections([]));
      fetchMatrix(preferredReportId).then(setMatrixRows).catch(() => setMatrixRows([]));
      fetchReportVersions(preferredReportId).then(setReportVersions).catch(() => setReportVersions([]));
    }
  }

  async function refreshDocuments() {
    if (!selectedOrganizationId) {
      return;
    }
    const items = await fetchDocuments(selectedOrganizationId);
    setDocuments(items);
  }

  async function handleCreateOrganization(payload: {
    name: string;
    short_name?: string;
    website?: string;
    email?: string;
    phone?: string;
  }) {
    const organization = await createOrganization(payload);
    const items = await fetchOrganizations();
    setOrganizations(items);
    setSelectedOrganizationId(organization.id);
  }

  async function handleUploadDocuments(payload: { files: File[]; category: string; tags?: string }) {
    if (!selectedOrganizationId) {
      throw new Error("Сначала выберите организацию в левой панели.");
    }
    await uploadDocuments(selectedOrganizationId, payload);
    await refreshDocuments();
  }

  async function handleSearchDocuments(query: string) {
    if (!selectedOrganizationId) {
      return;
    }
    const results = await searchDocuments(selectedOrganizationId, { query });
    setDocumentSearchResults(results);
  }

  async function handleProcessDocument(documentId: string) {
    await processDocument(documentId);
    await refreshDocuments();
  }

  async function handleCreateReport(payload: { title: string; report_type: string; selected_document_ids: string[] }) {
    if (!selectedOrganizationId) {
      return;
    }
    const report = await createReport(selectedOrganizationId, payload);
    await refreshOrganizationState(report.id);
  }

  async function handleAnalyzeReport(reportId: string) {
    await analyzeReport(reportId);
    await refreshOrganizationState(reportId);
  }

  async function handleGenerateReport(reportId: string) {
    await generateReport(reportId);
    await refreshOrganizationState(reportId);
  }

  async function handleSaveSection(reportId: string, sectionId: string, payload: { content: string }) {
    await updateSection(reportId, sectionId, payload);
    const freshSections = await fetchSections(reportId);
    setSections(freshSections);
  }

  async function handleConfirmRequirement(requirementId: string) {
    await confirmRequirement(requirementId);
    await refreshOrganizationState();
    setSelectedRequirementId(requirementId);
  }

  async function handleRejectRequirement(requirementId: string) {
    await rejectRequirement(requirementId);
    await refreshOrganizationState();
    setSelectedRequirementId(requirementId);
  }

  async function handleUpdateRequirement(
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
  ) {
    await updateRequirement(requirementId, payload);
    await refreshOrganizationState();
    setSelectedRequirementId(requirementId);
  }

  async function handleRefreshRequirementArtifacts(requirementId: string) {
    await refreshRequirementArtifacts(requirementId);
    await refreshOrganizationState();
    setSelectedRequirementId(requirementId);
  }

  async function handleBulkUpdateRequirements(payload: {
    requirement_ids: string[];
    status?: string;
    applicability_status?: string;
    user_comment?: string;
  }) {
    if (!selectedOrganizationId) {
      return;
    }
    await bulkUpdateRequirements(selectedOrganizationId, payload);
    await refreshOrganizationState();
  }

  async function handleMarkNotificationRead(notificationId: string) {
    await markNotificationRead(notificationId);
    await refreshOrganizationState();
  }

  async function handleMarkAllNotificationsRead() {
    if (!selectedOrganizationId) {
      return;
    }
    await markAllNotificationsRead(selectedOrganizationId);
    await refreshOrganizationState();
  }

  async function handleUpdateRisk(
    riskId: string,
    payload: { assigned_to_id?: string | null; status?: string; recommended_action?: string; description?: string },
  ) {
    await updateRisk(riskId, payload);
    await refreshOrganizationState();
  }

  async function handleResolveRisk(riskId: string) {
    await resolveRisk(riskId);
    await refreshOrganizationState();
  }

  async function handleRestoreReportVersion(versionId: string) {
    const report = await restoreReportVersion(versionId);
    await refreshOrganizationState(report.id);
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <Layout
            organizationId={selectedOrganizationId}
            onSelectOrganization={setSelectedOrganizationId}
            organizations={organizations}
            unreadNotifications={dashboard?.unread_notifications ?? notifications.filter((item) => item.status === "unread").length}
          />
        }
      >
        <Route index element={<DashboardPage dashboard={dashboard} notifications={notifications} />} />
        <Route
          path="organizations"
          element={
            <OrganizationsPage organizations={organizations} onCreateOrganization={handleCreateOrganization} />
          }
        />
        <Route
          path="documents"
          element={
            <DocumentsPage
              organizationName={selectedOrganization?.name ?? null}
              canUpload={Boolean(selectedOrganizationId)}
              documents={documents}
              searchResults={documentSearchResults}
              onUpload={handleUploadDocuments}
              onProcess={handleProcessDocument}
              onSearch={handleSearchDocuments}
            />
          }
        />
        <Route
          path="reports"
          element={
            <ReportsPage
              reports={reports}
              documents={documents}
              selectedReportId={selectedReportId}
              onSelectReport={setSelectedReportId}
              onCreateReport={handleCreateReport}
              onAnalyze={handleAnalyzeReport}
              onGenerate={handleGenerateReport}
              onExport={exportReport}
              onSubmitForApproval={async (reportId) => {
                await submitReportForApproval(reportId);
                await refreshOrganizationState(reportId);
              }}
              onApprove={async (reportId) => {
                await approveReport(reportId);
                await refreshOrganizationState(reportId);
              }}
              onReturnToRevision={async (reportId) => {
                await returnReportToRevision(reportId);
                await refreshOrganizationState(reportId);
              }}
            />
          }
        />
        <Route path="matrix" element={<MatrixPage rows={matrixRows} />} />
        <Route
          path="requirements"
          element={
            <RequirementsPage
              requirements={requirements}
              selectedRequirementId={selectedRequirementId}
              onSelectRequirement={setSelectedRequirementId}
              onConfirm={handleConfirmRequirement}
              onReject={handleRejectRequirement}
              onUpdateRequirement={handleUpdateRequirement}
              onBulkUpdate={handleBulkUpdateRequirements}
              onRefreshArtifacts={handleRefreshRequirementArtifacts}
            />
          }
        />
        <Route
          path="risks"
          element={
            <RisksPage
              risks={risks}
              members={members}
              onUpdateRisk={handleUpdateRisk}
              onResolveRisk={handleResolveRisk}
            />
          }
        />
        <Route
          path="notifications"
          element={
            <NotificationsPage
              notifications={notifications}
              onMarkRead={handleMarkNotificationRead}
              onMarkAllRead={handleMarkAllNotificationsRead}
            />
          }
        />
        <Route path="audit" element={<AuditLogPage logs={auditLogs} />} />
        <Route
          path="editor"
          element={
            <ReportEditorPage
              reportId={selectedReportId}
              sections={sections}
              versions={reportVersions}
              onSaveSection={handleSaveSection}
              onRestoreVersion={handleRestoreReportVersion}
            />
          }
        />
        <Route path="explanations" element={<ExplanationsPage explanation={explanation} />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  const token = getAccessToken();
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={token ? <AppShell /> : <Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
