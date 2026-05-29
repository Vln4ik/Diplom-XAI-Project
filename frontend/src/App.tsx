import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { FloatingXaiWidget } from "./components/FloatingXaiWidget";
import { Layout } from "./components/Layout";
import { PageGuideProvider } from "./components/PageGuideContext";
import {
  approveReport,
  analyzeReport,
  autofillOrganizationFromDocuments,
  confirmRequirement,
  createOrganization,
  createReport,
  deleteDocument,
  deleteOrganization,
  deleteReport,
  exportReport,
  fetchDashboard,
  fetchDocuments,
  fetchExplanation,
  fetchMembers,
  fetchMatrix,
  fetchNotifications,
  fetchOrganizations,
  fetchReports,
  fetchRequirements,
  refreshRequirementArtifacts,
  fetchRisks,
  generateReport,
  processDocument,
  rejectRequirement,
  resolveRisk,
  returnReportToRevision,
  submitReportForApproval,
  searchDocuments,
  updateOrganization,
  updateRequirement,
  updateRisk,
  uploadDocuments,
} from "./lib/api";
import { getAccessToken } from "./lib/session";
import { useLiveDocumentProgress, useLiveReportProgress } from "./lib/liveProgress";
import type {
  Dashboard,
  DocumentSearchMatch,
  DocumentItem,
  Explanation,
  MemberItem,
  NotificationItem,
  Organization,
  ReportItem,
  ReportMatrixRow,
  RequirementItem,
  RiskItem,
} from "./lib/types";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { ExplanationsPage } from "./pages/ExplanationsPage";
import { LoginPage } from "./pages/LoginPage";
import { MatrixPage } from "./pages/MatrixPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { RequirementsPage } from "./pages/RequirementsPage";
import { RisksPage } from "./pages/RisksPage";
import { clampProgress, getLiveDocumentProgressMeta, getLiveReportAnalysisProgress, type UiTask } from "./lib/ui";

function AppShell() {
  const location = useLocation();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [isXaiWidgetOpen, setIsXaiWidgetOpen] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [documentSearchResults, setDocumentSearchResults] = useState<DocumentSearchMatch[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [matrixRows, setMatrixRows] = useState<ReportMatrixRow[]>([]);
  const [requirements, setRequirements] = useState<RequirementItem[]>([]);
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [manualTasks, setManualTasks] = useState<UiTask[]>([]);
  const taskTimersRef = useRef<Record<string, number>>({});
  const selectedOrganization = organizations.find((organization) => organization.id === selectedOrganizationId) ?? null;
  const liveDocumentProgress = useLiveDocumentProgress(documents);
  const liveReportProgress = useLiveReportProgress(reports);
  const selectedRequirement = useMemo(
    () => requirements.find((requirement) => requirement.id === selectedRequirementId) ?? null,
    [requirements, selectedRequirementId],
  );
  const xaiWidgetRoutes: Record<string, string> = {
    "/reports": "Контекст отчета",
    "/matrix": "Контекст матрицы",
    "/requirements": "Контекст требования",
    "/risks": "Контекст риска",
  };
  const xaiWidgetRouteEntry = Object.entries(xaiWidgetRoutes).find(([route]) => location.pathname === route || location.pathname.startsWith(`${route}/`));
  const showXaiWidget = Boolean(xaiWidgetRouteEntry);
  const xaiWidgetRouteLabel = xaiWidgetRouteEntry?.[1] ?? "Рабочий контекст";

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
    const candidateReportId = arguments.length > 1 ? preferredReportId : selectedReportId;
    const nextReportId =
      candidateReportId && items.some((report) => report.id === candidateReportId)
        ? candidateReportId
        : items[0]?.id ?? null;
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
    setMatrixRows([]);
    setRequirements([]);
    setRisks([]);
    setMembers([]);
    setNotifications([]);
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
    reloadReports(selectedOrganizationId)
      .then(async (items) => {
        if (!items.nextReportId) {
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
      setMatrixRows([]);
      return;
    }
    fetchMatrix(selectedReportId).then(setMatrixRows).catch(() => setMatrixRows([]));
  }, [selectedReportId]);

  useEffect(() => {
    if (!selectedRequirementId) {
      setExplanation(null);
      return;
    }
    fetchExplanation(selectedRequirementId).then(setExplanation).catch(() => setExplanation(null));
  }, [selectedRequirementId]);

  useEffect(() => {
    if (!showXaiWidget) {
      setIsXaiWidgetOpen(false);
    }
  }, [showXaiWidget]);

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
      fetchDashboard(selectedOrganizationId).then(setDashboard).catch(() => undefined);
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
      fetchMatrix(preferredReportId).then(setMatrixRows).catch(() => setMatrixRows([]));
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

  async function handleUploadDocuments(payload: { files: File[]; category: string; tags?: string; relativePaths?: string[] }) {
    if (!selectedOrganizationId) {
      throw new Error("Сначала выберите организацию на вкладке «Организации».");
    }
    const hasFolderStructure = payload.relativePaths?.some((path) => path.includes("/")) ?? false;
    const taskId = `upload-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: hasFolderStructure ? "Загрузка папки документов" : "Загрузка документов",
        detail: `Загружаем ${payload.files.length} файл(ов) в организацию. После завершения они появятся в дереве и реестре документов.`,
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

  async function handleProcessDocumentFolder(documentIds: string[]) {
    const processableIds = documentIds.filter((documentId) => {
      const document = documents.find((item) => item.id === documentId);
      return document && !["queued", "processing"].includes(document.status);
    });
    if (processableIds.length === 0) {
      return;
    }

    const taskId = `process-folder-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: "Обработка ветки документов",
        detail: `Передаем в pipeline ${processableIds.length} файл(ов) из выбранной папки.`,
        progress: 14,
        tone: "info",
      },
      64,
    );
    try {
      await Promise.all(processableIds.map((documentId) => processDocument(documentId)));
      updateTask(taskId, {
        detail: "Файлы поставлены в очередь. Статусы ветки будут обновляться автоматически.",
        progress: 78,
      });
      await refreshDocuments();
    } finally {
      finishTask(taskId);
    }
  }

  async function handleDeleteDocument(document: DocumentItem) {
    if (!window.confirm(`Удалить файл «${document.file_name}» из проекта?`)) {
      return;
    }
    const taskId = `delete-document-${document.id}`;
    beginTask(
      {
        id: taskId,
        title: "Удаление документа",
        detail: `Удаляем файл «${document.file_name}» и связанные фрагменты из базы.`,
        progress: 18,
        tone: "warning",
      },
      78,
    );
    try {
      await deleteDocument(document.id);
      updateTask(taskId, {
        detail: "Документ удален. Обновляем дерево папок, отчеты и связанные показатели.",
        progress: 92,
        tone: "success",
      });
      await refreshDocuments();
      await refreshOrganizationState();
    } finally {
      finishTask(taskId);
    }
  }

  async function handleDeleteDocumentFolder(folderDocuments: DocumentItem[], folderPath: string) {
    if (folderDocuments.length === 0) {
      return;
    }
    if (!window.confirm(`Удалить папку «${folderPath}» и все файлы внутри (${folderDocuments.length})?`)) {
      return;
    }
    const taskId = `delete-folder-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: "Удаление папки документов",
        detail: `Удаляем ${folderDocuments.length} файл(ов) из ветки «${folderPath}».`,
        progress: 12,
        tone: "warning",
      },
      82,
    );
    try {
      for (const document of folderDocuments) {
        await deleteDocument(document.id);
      }
      updateTask(taskId, {
        detail: "Папка удалена. Обновляем реестр документов и отчеты.",
        progress: 94,
        tone: "success",
      });
      await refreshDocuments();
      await refreshOrganizationState();
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

  async function handleCreateAndAnalyzeReport(payload: { title: string; report_type: string; selected_document_ids: string[] }) {
    if (!selectedOrganizationId) {
      return;
    }
    const taskId = `create-analyze-report-${Date.now()}`;
    beginTask(
      {
        id: taskId,
        title: "Анализ папки документов",
        detail: `Создаем отчет по выбранной папке и запускаем анализ ${payload.selected_document_ids.length} документ(ов).`,
        progress: 12,
        tone: "info",
      },
      74,
    );
    try {
      const report = await createReport(selectedOrganizationId, payload);
      updateTask(taskId, {
        detail: "Отчет создан. Передаем папку в контур анализа требований, evidence и XAI.",
        progress: 42,
      });
      await analyzeReport(report.id);
      updateTask(taskId, {
        detail: "Анализ запущен. Обновляем отчеты, матрицу, требования и риски.",
        progress: 82,
      });
      await refreshOrganizationState(report.id);
    } finally {
      finishTask(taskId);
    }
  }

  async function handleDeleteReport(report: ReportItem) {
    if (!window.confirm(`Удалить отчет «${report.title}» и связанные результаты анализа?`)) {
      return;
    }
    const taskId = `delete-report-${report.id}`;
    beginTask(
      {
        id: taskId,
        title: "Удаление отчета",
        detail: `Удаляем отчет «${report.title}», матрицу, риски, XAI и export-связи.`,
        progress: 18,
        tone: "warning",
      },
      78,
    );
    try {
      await deleteReport(report.id);
      updateTask(taskId, {
        detail: "Отчет удален. Обновляем список отчетов и показатели организации.",
        progress: 92,
        tone: "success",
      });
      const nextReportId = selectedReportId === report.id ? null : selectedReportId;
      await refreshOrganizationState(nextReportId);
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
        detail: "Формируем текст разделов, версию черновика и данные для экспорта.",
        progress: 18,
        tone: "info",
      },
      72,
    );
    try {
      await generateReport(reportId);
      updateTask(taskId, {
        detail: "Разделы сформированы. Обновляем отчет, матрицу и связанные артефакты.",
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

  function handleInspectRequirement(requirementId: string) {
    setSelectedRequirementId(requirementId);
    setIsXaiWidgetOpen(true);
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

  const derivedTasks = useMemo(() => {
    const tasks: UiTask[] = [];
    const queuedDocuments = documents.filter((document) => document.status === "queued");
    const processingDocuments = documents.filter((document) => document.status === "processing");
    const analyzingReports = reports.filter((report) => report.status === "analyzing");

    if (queuedDocuments.length > 0 || processingDocuments.length > 0) {
      const totalActive = queuedDocuments.length + processingDocuments.length;
      const liveProgress =
        totalActive === 0
          ? 0
          : [...queuedDocuments, ...processingDocuments].reduce(
              (sum, document) =>
                sum + getLiveDocumentProgressMeta(document.status, liveDocumentProgress.getDocumentElapsedMs(document)).progress,
              0,
            ) / totalActive;
      tasks.push({
        id: "documents-pipeline",
        title: "Обработка документов",
        detail: `В очереди: ${queuedDocuments.length}. В обработке: ${processingDocuments.length}. После завершения обновятся поиск и фрагменты.`,
        currentItemName: liveDocumentProgress.currentDocument?.file_name,
        progress: clampProgress(liveProgress),
        tone: "warning",
      });
    }

    if (analyzingReports.length > 0) {
      const readinessMean =
        analyzingReports.reduce((sum, report) => sum + report.readiness_percent, 0) / analyzingReports.length;
      const liveAnalysisProgress = liveReportProgress.currentReport
        ? getLiveReportAnalysisProgress(readinessMean, liveReportProgress.getReportElapsedMs(liveReportProgress.currentReport))
        : readinessMean;
      tasks.push({
        id: "reports-analysis",
        title: "Анализ отчета",
        detail: `Анализируется ${analyzingReports.length} отчет(ов). После завершения обновятся требования, матрица, риски и XAI-объяснения.`,
        currentItemName: liveReportProgress.currentReport?.title,
        progress: clampProgress(liveAnalysisProgress),
        tone: "info",
      });
    }

    return tasks;
  }, [documents, liveDocumentProgress, liveReportProgress, reports]);

  const activeTasks = useMemo(() => [...manualTasks, ...derivedTasks], [derivedTasks, manualTasks]);

  return (
    <PageGuideProvider>
      <Routes>
      <Route
        path="/"
        element={
          <Layout
            organizationName={selectedOrganization?.name ?? null}
            activeTasks={activeTasks}
            floatingWidget={
              showXaiWidget ? (
                <FloatingXaiWidget
                  explanation={explanation}
                  requirement={selectedRequirement}
                  isOpen={isXaiWidgetOpen}
                  onToggle={() => setIsXaiWidgetOpen((current) => !current)}
                  routeLabel={xaiWidgetRouteLabel}
                />
              ) : null
            }
          />
        }
      >
        <Route
          index
          element={<DashboardPage dashboard={dashboard} documents={documents} reports={reports} requirements={requirements} risks={risks} />}
        />
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
              onProcessFolder={handleProcessDocumentFolder}
              onDeleteDocument={handleDeleteDocument}
              onDeleteFolder={handleDeleteDocumentFolder}
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
              onCreateAndAnalyzeReport={handleCreateAndAnalyzeReport}
              onDeleteReport={handleDeleteReport}
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
        <Route
          path="matrix"
          element={
            <MatrixPage rows={matrixRows} selectedRequirementId={selectedRequirementId} onSelectRequirement={handleInspectRequirement} />
          }
        />
        <Route
          path="requirements"
          element={
            <RequirementsPage
              requirements={requirements}
              selectedRequirementId={selectedRequirementId}
              onSelectRequirement={handleInspectRequirement}
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
              selectedRequirementId={selectedRequirementId}
              onSelectRequirement={handleInspectRequirement}
              onUpdateRisk={handleUpdateRisk}
              onResolveRisk={handleResolveRisk}
            />
          }
        />
        <Route path="explanations" element={<ExplanationsPage explanation={explanation} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
      </Routes>
    </PageGuideProvider>
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
