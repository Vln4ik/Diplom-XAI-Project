import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import {
  approveReport,
  analyzeReport,
  autofillOrganizationFromDocuments,
  confirmRequirement,
  createOrganization,
  createReport,
  deleteOrganization,
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
  updateOrganization,
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
import { buildDashboardSignals, clampProgress, type UiTask } from "./lib/ui";

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
  const [manualTasks, setManualTasks] = useState<UiTask[]>([]);
  const taskTimersRef = useRef<Record<string, number>>({});
  const selectedOrganization = organizations.find((organization) => organization.id === selectedOrganizationId) ?? null;

  async function reloadOrganizations(preferredOrganizationId?: string | null) {
    const items = await fetchOrganizations();
    setOrganizations(items);
    const nextOrganizationId =
      preferredOrganizationId && items.some((organization) => organization.id === preferredOrganizationId)
        ? preferredOrganizationId
        : items[0]?.id ?? null;
    setSelectedOrganizationId(nextOrganizationId);
    return { items, nextOrganizationId };
  }

  function clearTaskTimer(taskId: string) {
    const timerId = taskTimersRef.current[taskId];
    if (timerId) {
      window.clearInterval(timerId);
      delete taskTimersRef.current[taskId];
    }
  }

  function beginTask(task: UiTask, ceiling = 84) {
    clearTaskTimer(task.id);
    setManualTasks((current) => [...current.filter((item) => item.id !== task.id), task]);
    taskTimersRef.current[task.id] = window.setInterval(() => {
      setManualTasks((current) =>
        current.map((item) =>
          item.id === task.id
            ? {
                ...item,
                progress: item.progress >= ceiling ? item.progress : clampProgress(item.progress + Math.max(2, (ceiling - item.progress) * 0.12)),
              }
            : item,
        ),
      );
    }, 700);
  }

  function updateTask(taskId: string, patch: Partial<UiTask>) {
    setManualTasks((current) => current.map((item) => (item.id === taskId ? { ...item, ...patch } : item)));
  }

  function finishTask(taskId: string) {
    clearTaskTimer(taskId);
    setManualTasks((current) => current.filter((item) => item.id !== taskId));
  }

  async function reloadReports(organizationId: string, preferredReportId?: string | null) {
    const items = await fetchReports(organizationId);
    setReports(items);
    const nextReportId = preferredReportId ?? selectedReportId ?? items[0]?.id ?? null;
    setSelectedReportId(nextReportId);
    return { items, nextReportId };
  }

  useEffect(() => {
    reloadOrganizations().catch(() => undefined);
  }, []);

  useEffect(
    () => () => {
      for (const timerId of Object.values(taskTimersRef.current)) {
        window.clearInterval(timerId);
      }
      taskTimersRef.current = {};
    },
    [],
  );

  useEffect(() => {
    if (selectedOrganizationId) {
      return;
    }
    setDashboard(null);
    setDocuments([]);
    setDocumentSearchResults([]);
    setReports([]);
    setReportVersions([]);
    setMatrixRows([]);
    setRequirements([]);
    setRisks([]);
    setMembers([]);
    setNotifications([]);
    setAuditLogs([]);
    setSections([]);
    setExplanation(null);
    setSelectedReportId(null);
    setSelectedRequirementId(null);
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
  }) {
    const organization = await createOrganization(payload);
    await reloadOrganizations(organization.id);
  }

  async function handleUpdateOrganization(
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
  ) {
    await updateOrganization(organizationId, payload);
    await reloadOrganizations(selectedOrganizationId ?? organizationId);
    if (selectedOrganizationId === organizationId) {
      fetchDashboard(organizationId).then(setDashboard).catch(() => setDashboard(null));
    }
  }

  async function handleDeleteOrganization(organizationId: string) {
    await deleteOrganization(organizationId);
    const preferredOrganizationId = selectedOrganizationId === organizationId ? null : selectedOrganizationId;
    await reloadOrganizations(preferredOrganizationId);
  }

  async function handleAutofillOrganization(organizationId: string) {
    return autofillOrganizationFromDocuments(organizationId);
  }

  async function handleUploadDocuments(payload: { files: File[]; category: string; tags?: string }) {
    if (!selectedOrganizationId) {
      throw new Error("Сначала выберите организацию в левой панели.");
    }
    const taskId = `upload-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: "Загрузка документов",
        detail: `Загружаем ${payload.files.length} файл(ов) в организацию. После завершения они появятся в реестре документов.`,
        progress: 12,
        tone: "info",
      },
      78,
    );
    try {
      await uploadDocuments(selectedOrganizationId, payload);
      updateTask(taskId, {
        detail: "Файлы приняты. Обновляем реестр документов и статусы.",
        progress: 88,
        tone: "success",
      });
      await refreshDocuments();
    } finally {
      finishTask(taskId);
    }
  }

  async function handleSearchDocuments(query: string) {
    if (!selectedOrganizationId) {
      return;
    }
    const results = await searchDocuments(selectedOrganizationId, { query });
    setDocumentSearchResults(results);
  }

  async function handleProcessDocument(documentId: string) {
    const taskId = `process-document-${documentId}`;
    beginTask(
      {
        id: taskId,
        title: "Постановка документа в обработку",
        detail: "Документ передается в pipeline извлечения текста, chunking и индексации.",
        progress: 18,
        tone: "info",
      },
      46,
    );
    try {
      await processDocument(documentId);
      updateTask(taskId, {
        detail: "Документ поставлен в очередь. Дальше прогресс будет идти автоматически по статусам pipeline.",
        progress: 52,
      });
      await refreshDocuments();
    } finally {
      finishTask(taskId);
    }
  }

  async function handleCreateReport(payload: { title: string; report_type: string; selected_document_ids: string[] }) {
    if (!selectedOrganizationId) {
      return;
    }
    const taskId = `create-report-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: "Создание отчета",
        detail: "Создаем карточку отчета и привязываем выбранные документы.",
        progress: 18,
        tone: "info",
      },
      74,
    );
    try {
      const report = await createReport(selectedOrganizationId, payload);
      updateTask(taskId, {
        detail: "Отчет создан. Обновляем связанные разделы интерфейса.",
        progress: 88,
        tone: "success",
      });
      await refreshOrganizationState(report.id);
    } finally {
      finishTask(taskId);
    }
  }

  async function handleAnalyzeReport(reportId: string) {
    const taskId = `analyze-report-${reportId}`;
    beginTask(
      {
        id: taskId,
        title: "Запуск анализа отчета",
        detail: "Система выделяет требования, ищет evidence, считает confidence, риски и XAI-объяснения.",
        progress: 16,
        tone: "info",
      },
      68,
    );
    try {
      await analyzeReport(reportId);
      updateTask(taskId, {
        detail: "Анализ поставлен в работу. Обновляем требования, матрицу и риски.",
        progress: 82,
      });
      await refreshOrganizationState(reportId);
    } finally {
      finishTask(taskId);
    }
  }

  async function handleGenerateReport(reportId: string) {
    const taskId = `generate-report-${reportId}`;
    beginTask(
      {
        id: taskId,
        title: "Генерация разделов отчета",
        detail: "Формируем текст разделов, версии отчета и данные для редактора.",
        progress: 18,
        tone: "info",
      },
      72,
    );
    try {
      await generateReport(reportId);
      updateTask(taskId, {
        detail: "Разделы сформированы. Обновляем редактор и версии отчета.",
        progress: 90,
        tone: "success",
      });
      await refreshOrganizationState(reportId);
    } finally {
      finishTask(taskId);
    }
  }

  async function handleExportReport(reportId: string, exportType: "docx" | "matrix" | "package" | "explanations") {
    const taskId = `export-${exportType}-${reportId}`;
    beginTask(
      {
        id: taskId,
        title: "Подготовка экспорта",
        detail: `Формируем файл экспорта типа ${exportType.toUpperCase()} и подготавливаем скачивание.`,
        progress: 18,
        tone: "info",
      },
      82,
    );
    try {
      await exportReport(reportId, exportType);
    } finally {
      finishTask(taskId);
    }
  }

  async function handleSaveSection(reportId: string, sectionId: string, payload: { content: string }) {
    const taskId = `save-section-${sectionId}`;
    beginTask(
      {
        id: taskId,
        title: "Сохранение раздела",
        detail: "Обновляем текст раздела и синхронизируем редактор с сервером.",
        progress: 28,
        tone: "info",
      },
      86,
    );
    try {
      await updateSection(reportId, sectionId, payload);
      const freshSections = await fetchSections(reportId);
      setSections(freshSections);
    } finally {
      finishTask(taskId);
    }
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
    const taskId = `restore-version-${versionId}`;
    beginTask(
      {
        id: taskId,
        title: "Восстановление версии",
        detail: "Возвращаем сохраненное состояние разделов, матрицы и XAI-артефактов.",
        progress: 24,
        tone: "warning",
      },
      84,
    );
    try {
      const report = await restoreReportVersion(versionId);
      await refreshOrganizationState(report.id);
    } finally {
      finishTask(taskId);
    }
  }

  const derivedTasks = useMemo(() => {
    const tasks: UiTask[] = [];
    const queuedDocuments = documents.filter((document) => document.status === "queued");
    const processingDocuments = documents.filter((document) => document.status === "processing");
    const analyzingReports = reports.filter((report) => report.status === "analyzing");

    if (queuedDocuments.length > 0 || processingDocuments.length > 0) {
      const totalActive = queuedDocuments.length + processingDocuments.length;
      const weightedProgress =
        totalActive === 0
          ? 0
          : (queuedDocuments.length * 28 + processingDocuments.length * 68) / totalActive;
      tasks.push({
        id: "documents-pipeline",
        title: "Обработка документов",
        detail: `В очереди: ${queuedDocuments.length}. В обработке: ${processingDocuments.length}. После завершения обновятся поиск и фрагменты.`,
        progress: clampProgress(weightedProgress),
        tone: "warning",
      });
    }

    if (analyzingReports.length > 0) {
      const readinessMean =
        analyzingReports.reduce((sum, report) => sum + report.readiness_percent, 0) / analyzingReports.length;
      tasks.push({
        id: "reports-analysis",
        title: "Анализ отчета",
        detail: `Анализируется ${analyzingReports.length} отчет(ов). После завершения обновятся требования, матрица, риски и XAI-объяснения.`,
        progress: clampProgress(Math.max(42, Math.min(88, readinessMean * 0.7 + 28))),
        tone: "info",
      });
    }

    return tasks;
  }, [documents, reports]);

  const activeTasks = useMemo(() => [...manualTasks, ...derivedTasks], [derivedTasks, manualTasks]);

  const dashboardSignals = useMemo(
    () =>
      buildDashboardSignals({
        dashboard,
        notifications,
        documents,
        reports,
        requirements,
        risks,
      }),
    [dashboard, notifications, documents, reports, requirements, risks],
  );

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
            activeTasks={activeTasks}
          />
        }
      >
        <Route index element={<DashboardPage dashboard={dashboard} notifications={notifications} signals={dashboardSignals} />} />
        <Route
          path="organizations"
          element={
            <OrganizationsPage
              organizations={organizations}
              selectedOrganizationId={selectedOrganizationId}
              onSelectOrganization={setSelectedOrganizationId}
              onCreateOrganization={handleCreateOrganization}
              onUpdateOrganization={handleUpdateOrganization}
              onDeleteOrganization={handleDeleteOrganization}
              onAutofillOrganization={handleAutofillOrganization}
            />
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
              onExport={handleExportReport}
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
