import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { DocumentFolderTree } from "../components/DocumentFolderTree";
import { EstimateWorkflowPanel } from "../components/EstimateWorkflowPanel";
import { PageGuide } from "../components/PageGuide";
import { fetchEstimateExpertiseWorkflow } from "../lib/api";
import {
  buildDocumentFolderTree,
  summarizeFolderDocuments,
} from "../lib/documentTree";
import {
  buildEstimateExpertiseWorkflowPlaceholder,
  type EstimateExpertiseFinding,
  type EstimateExpertiseStage,
  type EstimateExpertiseWorkflow,
  type ExpertiseStageStatus,
} from "../lib/estimateExpertise";
import { useLiveReportProgress } from "../lib/liveProgress";
import {
  getStateExpertiseRegulationLabel,
  getReportTypeDefaultTitle,
  isStateExpertiseEstimateCostReport,
  REPORT_TYPE_OPTIONS,
  REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87,
} from "../lib/reportTypes";
import type { DocumentItem, ReportItem } from "../lib/types";
import {
  formatReportStatus,
  formatReportType,
  getLiveReportAnalysisProgress,
  getReadinessMeta,
} from "../lib/ui";

type Props = {
  organizationId: string | null;
  reports: ReportItem[];
  documents: DocumentItem[];
  selectedReportId: string | null;
  onSelectReport: (reportId: string) => void;
  onCreateReport: (payload: { title: string; report_type: string; selected_document_ids: string[] }) => Promise<void>;
  onCreateAndAnalyzeReport: (payload: { title: string; report_type: string; selected_document_ids: string[] }) => Promise<void>;
  onDeleteReport: (report: ReportItem) => Promise<void>;
  onAnalyze: (reportId: string) => Promise<void>;
  onGenerate: (reportId: string) => Promise<void>;
  onExport: (reportId: string, exportType: "docx" | "matrix" | "package" | "explanations") => Promise<void>;
  onSubmitForApproval: (reportId: string) => Promise<void>;
  onApprove: (reportId: string) => Promise<void>;
  onReturnToRevision: (reportId: string) => Promise<void>;
  estimateWorkflowByReportId: Record<string, EstimateExpertiseWorkflow>;
  onEstimateWorkflowUpdate: (reportId: string, workflow: EstimateExpertiseWorkflow) => void;
};

type StoredReportsPageState = {
  title?: string;
  reportType?: string;
  selectedDocumentIds?: string[];
  inspectedDocumentId?: string | null;
  openFolderPaths?: string[];
};

const REPORTS_PAGE_STATE_STORAGE_PREFIX = "evidencexai:reports-page-state";
const DEFAULT_REPORT_TITLE = "Отчет о готовности к проверке";
const DEFAULT_REPORT_TYPE = "readiness_report";

function getReportsPageStateStorageKey(organizationId: string | null): string {
  return `${REPORTS_PAGE_STATE_STORAGE_PREFIX}:${organizationId ?? "global"}`;
}

function readReportsPageState(organizationId: string | null): StoredReportsPageState | null {
  try {
    const raw = window.localStorage.getItem(getReportsPageStateStorageKey(organizationId));
    return raw ? JSON.parse(raw) as StoredReportsPageState : null;
  } catch {
    return null;
  }
}

function writeReportsPageState(organizationId: string | null, state: StoredReportsPageState) {
  window.localStorage.setItem(getReportsPageStateStorageKey(organizationId), JSON.stringify(state));
}

const EXPORT_OPTIONS: Array<{ value: "docx" | "matrix" | "package" | "explanations"; label: string; hint: string }> = [
  { value: "docx", label: "DOCX", hint: "Проект отчета" },
  { value: "matrix", label: "XLSX", hint: "Матрица требований" },
  { value: "package", label: "ZIP", hint: "Пакет доказательств" },
  { value: "explanations", label: "XAI HTML", hint: "Объяснения и логика" },
];

const ESTIMATE_EXPORT_OPTIONS: Array<{ value: "docx" | "matrix" | "package" | "explanations"; label: string; hint: string }> = [
  { value: "docx", label: "DOCX", hint: "Summary спецпроверки" },
  { value: "matrix", label: "XLSX", hint: "Матрица findings" },
  { value: "package", label: "ZIP", hint: "Workflow + доказательства" },
  { value: "explanations", label: "XAI HTML", hint: "XAI по каждому выводу" },
];

function getEstimateCostStages(reportType: string): string[] {
  const regulationLabel = getStateExpertiseRegulationLabel(reportType);
  const baseStages = ["Запуск", "Название и содержание"];
  if (reportType === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87) {
    baseStages.push(`Содержание разделов по ${regulationLabel}`);
  } else {
    baseStages.push(`Комплектность по ${regulationLabel}`);
  }
  return [...baseStages, "Лексика, орфография, подписи", "Финальная готовность"];
}

function formatRealtimeEta(totalSeconds: number): string {
  if (totalSeconds <= 0) {
    return "ожидает выбора";
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${seconds} сек`;
  }
  return `${minutes} мин ${seconds.toString().padStart(2, "0")} сек`;
}

const STAGE_STATUS_LABELS: Record<ExpertiseStageStatus, string> = {
  completed: "Завершено",
  running: "В работе",
  blocked: "Требует решения",
  pending: "Ожидает",
};

type EstimateRailStage = Pick<EstimateExpertiseStage, "id" | "order" | "shortTitle" | "status" | "progress" | "checkedFiles" | "totalFiles">;
type StageWorkItem = { name: string; detail: string; progress: number; tone: "info" | "warning" | "success" };

function getRotatingWindow<T>(items: T[], tick: number, size: number): T[] {
  if (items.length <= size) {
    return items;
  }
  const start = tick % items.length;
  return Array.from({ length: size }, (_, index) => items[(start + index) % items.length]);
}

function buildPreviewEstimateStages(reportType: string): EstimateRailStage[] {
  return getEstimateCostStages(reportType).map((title, index) => {
    return {
      id: `preview-${index + 1}`,
      order: index + 1,
      shortTitle: title,
      status: "pending",
      progress: 0,
      checkedFiles: 0,
      totalFiles: 0,
    };
  });
}

function getCurrentEstimateStage(stages: EstimateRailStage[]): EstimateRailStage | null {
  return stages.find((stage) => stage.status !== "completed") ?? stages[stages.length - 1] ?? null;
}

function normalizeEstimateRailStagesForDisplay(stages: EstimateRailStage[]): EstimateRailStage[] {
  let reachedCurrentStage = false;
  return stages.map((stage) => {
    if (reachedCurrentStage) {
      return {
        ...stage,
        status: "pending",
        progress: 0,
        checkedFiles: 0,
      };
    }

    if (stage.status !== "completed") {
      reachedCurrentStage = true;
    }

    return stage;
  });
}

function getEstimateRailProgress(stages: EstimateRailStage[]): number {
  if (stages.length <= 1) {
    return stages[0]?.status === "completed" ? 100 : 0;
  }
  const currentIndex = stages.findIndex((stage) => stage.status !== "completed");
  if (currentIndex === -1) {
    return 100;
  }
  if (currentIndex <= 0) {
    return 0;
  }
  return Math.round((currentIndex / (stages.length - 1)) * 100);
}

function estimateCurrentStageEtaSeconds(stage: EstimateRailStage | null, selectedDocumentsCount: number, hasActiveWorkflow: boolean): number {
  if (!hasActiveWorkflow || !stage || stage.status === "completed" || stage.status === "blocked" || stage.status === "pending") {
    return 0;
  }
  const fileCount = Math.max(1, stage.totalFiles || selectedDocumentsCount);
  const remainingStageWork = Math.max(5, 100 - stage.progress);
  return Math.ceil(fileCount * 3 + remainingStageWork * 0.28);
}

function formatStageEta(stage: EstimateRailStage | null, seconds: number, hasActiveWorkflow: boolean): string {
  if (!hasActiveWorkflow) {
    return "ожидает запуска";
  }
  if (!stage) {
    return "ожидает выбора";
  }
  if (stage.status === "completed") {
    return "этап завершен";
  }
  if (stage.status === "blocked") {
    return "ожидает решения пользователя";
  }
  return formatRealtimeEta(seconds);
}

function isClosedReport(report: ReportItem): boolean {
  return ["approved", "exported", "archived"].includes(report.status);
}

function isWorkflowComplete(workflow: EstimateExpertiseWorkflow | null): boolean {
  if (!workflow) {
    return false;
  }
  const finalStage = workflow.stages.find((stage) => stage.id === "final");
  return workflow.status === "completed" || Boolean(finalStage && finalStage.status === "completed" && workflow.unresolvedFindings === 0);
}

function isFindingResolved(finding: EstimateExpertiseFinding): boolean {
  return Boolean(finding.decision && finding.decision.status !== "replacement_processing");
}

function getWorkflowForReport(
  report: ReportItem,
  documents: DocumentItem[],
  workflowByReportId: Record<string, EstimateExpertiseWorkflow>,
): EstimateExpertiseWorkflow {
  const cachedWorkflow = workflowByReportId[report.id];
  if (cachedWorkflow) {
    return cachedWorkflow;
  }
  const fallbackWorkflow = buildEstimateExpertiseWorkflowPlaceholder(report, documents);
  return isReportReadyByBackend(report) ? markWorkflowComplete(fallbackWorkflow) : fallbackWorkflow;
}

function isReportReadyByBackend(report: ReportItem): boolean {
  return report.readiness_percent >= 100 || ["awaiting_approval", "approved", "exported", "archived"].includes(report.status);
}

function markWorkflowComplete(workflow: EstimateExpertiseWorkflow): EstimateExpertiseWorkflow {
  return {
    ...workflow,
    status: "completed",
    progress: 100,
    checkedFiles: workflow.totalFiles,
    unresolvedFindings: 0,
    stages: workflow.stages.map((stage) => ({
      ...stage,
      status: "completed",
      progress: 100,
      checkedFiles: stage.totalFiles,
    })),
  };
}

function getReportSourceDocuments(report: ReportItem | null, documents: DocumentItem[], selectedDocuments: DocumentItem[]): DocumentItem[] {
  if (!report) {
    return selectedDocuments;
  }
  const selectedIds = new Set(report.selected_document_ids ?? []);
  return selectedIds.size > 0
    ? documents.filter((document) => selectedIds.has(document.id))
    : documents.filter((document) => ["processed", "requires_review"].includes(document.status));
}

function getStageWorkItems(
  stage: EstimateRailStage | null,
  workflow: EstimateExpertiseWorkflow | null,
  sourceDocuments: DocumentItem[],
  tick: number,
): { items: StageWorkItem[]; total: number } {
  if (!stage) {
    return { items: [], total: 0 };
  }
  const workflowStage = workflow?.stages.find((item) => item.id === stage.id);
  const unresolvedFindings = (workflowStage?.findings ?? []).filter((finding) => finding.severity !== "info" && !isFindingResolved(finding));
  if (stage.status === "blocked" && unresolvedFindings.length > 0) {
    return {
      items: getRotatingWindow(unresolvedFindings, tick, 4).map((finding) => ({
        name: finding.documentName,
        detail: "требуется решение пользователя",
        progress: 100,
        tone: "warning" as const,
      })),
      total: unresolvedFindings.length,
    };
  }

  if (!workflow || stage.status === "pending") {
    return { items: [], total: 0 };
  }

  const documentsWithIndex = sourceDocuments.map((document, index) => ({ document, index }));
  const visibleDocuments = getRotatingWindow(documentsWithIndex, tick + stage.order * 2, 4);
  const backendCheckedFiles = stage.status === "completed" ? sourceDocuments.length : Math.min(stage.checkedFiles, sourceDocuments.length);
  const visualCheckedFiles =
    stage.status === "running" && sourceDocuments.length > 0
      ? Math.min(sourceDocuments.length, tick % (sourceDocuments.length + 1))
      : backendCheckedFiles;

  return {
    items: visibleDocuments.map(({ document, index }) => {
      const isChecked = stage.status === "completed" || index < visualCheckedFiles;
      const isCurrent = stage.status === "running" && index === visualCheckedFiles;
      const progress = isChecked ? 100 : isCurrent ? Math.max(12, Math.min(92, stage.progress)) : 0;
      const tone = isChecked ? "success" as const : "info" as const;
      return {
        name: document.file_name,
        detail: isChecked ? "проверен на текущем этапе" : isCurrent ? "проверяется сейчас" : "ожидает текущий этап",
        progress,
        tone,
      };
    }),
    total: sourceDocuments.length,
  };
}

function getDocumentIssueItems(document: DocumentItem | null): Array<{ tone: "success" | "warning" | "danger" | "info"; title: string; detail: string }> {
  if (!document) {
    return [
      {
        tone: "info",
        title: "Файл не выбран",
        detail: "Откройте папку и нажмите на файл: здесь появятся ошибки обработки и замечания модели по выбранному источнику.",
      },
    ];
  }
  const items: Array<{ tone: "success" | "warning" | "danger" | "info"; title: string; detail: string }> = [];
  if (document.processing_error) {
    items.push({
      tone: "danger",
      title: "Ошибка обработки",
      detail: document.processing_error,
    });
  }
  if (document.status === "failed") {
    items.push({
      tone: "danger",
      title: "Pipeline завершился с ошибкой",
      detail: "Файл нужно заменить, удалить или повторно отправить в обработку после проверки формата.",
    });
  }
  if (document.status === "requires_review") {
    items.push({
      tone: "warning",
      title: "Требуется ручная проверка",
      detail: "Текст извлечен, но качество или структура документа требуют контроля специалиста перед финальным выводом.",
    });
  }
  if (["queued", "processing", "uploaded"].includes(document.status)) {
    items.push({
      tone: "info",
      title: "Проверка еще не завершена",
      detail: "Ошибки анализа будут доступны после завершения pipeline и запуска отчета по выбранной папке.",
    });
  }
  if (items.length === 0) {
    items.push({
      tone: "success",
      title: "Критичных ошибок обработки не найдено",
      detail: "Файл готов к включению в отчет. Предметные замечания появятся после запуска специализированного workflow.",
    });
  }
  return items;
}

export function ReportsPage({
  organizationId,
  reports,
  documents,
  selectedReportId,
  onSelectReport,
  onCreateReport,
  onCreateAndAnalyzeReport,
  onDeleteReport,
  onAnalyze,
  onGenerate,
  onExport,
  onSubmitForApproval,
  onApprove,
  onReturnToRevision,
  estimateWorkflowByReportId,
  onEstimateWorkflowUpdate,
}: Props) {
  const [title, setTitle] = useState(DEFAULT_REPORT_TITLE);
  const [reportType, setReportType] = useState(DEFAULT_REPORT_TYPE);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [exportMenuReportId, setExportMenuReportId] = useState<string | null>(null);
  const [selectionRailProgress, setSelectionRailProgress] = useState(0);
  const [stageEtaSecondsRemaining, setStageEtaSecondsRemaining] = useState(0);
  const [currentWorkTick, setCurrentWorkTick] = useState(0);
  const [inspectedDocumentId, setInspectedDocumentId] = useState<string | null>(null);
  const [openFolderPaths, setOpenFolderPaths] = useState<string[]>([]);
  const hydratedStateKeyRef = useRef<string | null>(null);
  const isSpecialEstimateCostReport = isStateExpertiseEstimateCostReport(reportType);
  const { getReportElapsedMs } = useLiveReportProgress(reports);

  useEffect(() => {
    const missingSpecialReports = reports.filter(
      (report) => isStateExpertiseEstimateCostReport(report.report_type) && !estimateWorkflowByReportId[report.id],
    );
    if (missingSpecialReports.length === 0) {
      return;
    }

    let cancelled = false;
    Promise.allSettled(
      missingSpecialReports.map(async (report) => ({
        reportId: report.id,
        workflow: await fetchEstimateExpertiseWorkflow(report.id),
      })),
    ).then((results) => {
      if (cancelled) {
        return;
      }
      const nextEntries = results
        .filter((result): result is PromiseFulfilledResult<{ reportId: string; workflow: EstimateExpertiseWorkflow }> => result.status === "fulfilled")
        .map((result) => [result.value.reportId, result.value.workflow] as const);
      for (const [reportId, workflow] of nextEntries) {
        onEstimateWorkflowUpdate(reportId, workflow);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [estimateWorkflowByReportId, onEstimateWorkflowUpdate, reports]);

  const processedDocuments = useMemo(
    () => documents.filter((document) => ["processed", "requires_review"].includes(document.status)),
    [documents],
  );
  const allFolderTree = useMemo(() => buildDocumentFolderTree(documents), [documents]);
  const selectedDocuments = useMemo(
    () => documents.filter((document) => selectedDocumentIds.includes(document.id)),
    [documents, selectedDocumentIds],
  );
  const inspectedDocument = useMemo(
    () => documents.find((document) => document.id === inspectedDocumentId) ?? null,
    [documents, inspectedDocumentId],
  );
  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedReportId) ?? null,
    [reports, selectedReportId],
  );
  const activeSpecialReportForType = useMemo(
    () =>
      reports.find((report) => {
        if (
          report.report_type !== reportType ||
          !isStateExpertiseEstimateCostReport(report.report_type) ||
          isClosedReport(report)
        ) {
          return false;
        }
        return !isWorkflowComplete(getWorkflowForReport(report, documents, estimateWorkflowByReportId));
      }) ?? null,
    [documents, estimateWorkflowByReportId, reportType, reports],
  );
  const selectedSpecialReport = selectedReport && isStateExpertiseEstimateCostReport(selectedReport.report_type) ? selectedReport : null;
  const activeSpecialWorkflow = activeSpecialReportForType
    ? getWorkflowForReport(activeSpecialReportForType, documents, estimateWorkflowByReportId)
    : null;
  const reviewSpecialReport =
    activeSpecialReportForType ?? (selectedDocumentIds.length === 0 ? selectedSpecialReport : null);
  const reviewSpecialWorkflow = reviewSpecialReport
    ? getWorkflowForReport(reviewSpecialReport, documents, estimateWorkflowByReportId)
    : null;
  const hasBlockingSpecialWorkflowForType = Boolean(activeSpecialReportForType && !isWorkflowComplete(activeSpecialWorkflow));
  const displayEstimateReportType = reportType;
  const estimateRegulationLabel = getStateExpertiseRegulationLabel(displayEstimateReportType);
  const showEstimateWorkflowGraph = isSpecialEstimateCostReport && (selectedDocumentIds.length > 0 || Boolean(activeSpecialReportForType));
  const selectedSummary = summarizeFolderDocuments(selectedDocuments);
  const activeWorkflowSourceDocuments = getReportSourceDocuments(activeSpecialReportForType, documents, selectedDocuments);
  const estimateRailStages: EstimateRailStage[] = normalizeEstimateRailStagesForDisplay(
    activeSpecialWorkflow?.stages ?? buildPreviewEstimateStages(displayEstimateReportType),
  );
  const currentEstimateStage = getCurrentEstimateStage(estimateRailStages);
  const selectionRailTarget = getEstimateRailProgress(estimateRailStages);
  const currentStageEtaTarget = estimateCurrentStageEtaSeconds(
    currentEstimateStage,
    activeWorkflowSourceDocuments.length,
    Boolean(activeSpecialReportForType),
  );
  const currentStageEtaLabel = formatStageEta(currentEstimateStage, stageEtaSecondsRemaining, Boolean(activeSpecialReportForType));
  const currentStageWorkItemsResult = getStageWorkItems(currentEstimateStage, activeSpecialWorkflow, activeWorkflowSourceDocuments, currentWorkTick);
  const currentStageWorkItems = currentStageWorkItemsResult.items;
  const hiddenWorkItemsCount = Math.max(0, currentStageWorkItemsResult.total - currentStageWorkItems.length);
  const fullyReadyFilesCount = isWorkflowComplete(activeSpecialWorkflow) ? activeWorkflowSourceDocuments.length : 0;
  const totalWorkflowFiles = activeSpecialReportForType ? activeWorkflowSourceDocuments.length : selectedSummary.total;
  const currentStageCheckedFiles = currentEstimateStage?.checkedFiles ?? 0;
  const currentStageTotalFiles = currentEstimateStage?.totalFiles || totalWorkflowFiles;
  const visualCurrentStageCheckedFiles =
    activeSpecialReportForType && currentEstimateStage?.status === "running" && currentStageTotalFiles > 0
      ? Math.min(currentStageTotalFiles, currentWorkTick % (currentStageTotalFiles + 1))
      : currentStageCheckedFiles;
  const inspectedIssues = getDocumentIssueItems(inspectedDocument);

  useEffect(() => {
    hydratedStateKeyRef.current = null;
    setTitle(DEFAULT_REPORT_TITLE);
    setReportType(DEFAULT_REPORT_TYPE);
    setSelectedDocumentIds([]);
    setInspectedDocumentId(null);
    setOpenFolderPaths([]);
    setExportMenuReportId(null);
  }, [organizationId]);

  useEffect(() => {
    const storageKey = getReportsPageStateStorageKey(organizationId);
    if (hydratedStateKeyRef.current === storageKey) {
      return;
    }

    const stored = readReportsPageState(organizationId);
    if (!stored && allFolderTree.length === 0) {
      return;
    }

    const validReportType = stored?.reportType && REPORT_TYPE_OPTIONS.some((option) => option.value === stored.reportType)
      ? stored.reportType
      : DEFAULT_REPORT_TYPE;
    const knownDocumentIds = new Set(documents.map((document) => document.id));
    const nextSelectedDocumentIds =
      documents.length > 0
        ? (stored?.selectedDocumentIds ?? []).filter((documentId) => knownDocumentIds.has(documentId))
        : stored?.selectedDocumentIds ?? [];
    const nextInspectedDocumentId =
      stored?.inspectedDocumentId && (documents.length === 0 || knownDocumentIds.has(stored.inspectedDocumentId))
        ? stored.inspectedDocumentId
        : null;

    setTitle(stored?.title || getReportTypeDefaultTitle(validReportType));
    setReportType(validReportType);
    setSelectedDocumentIds(nextSelectedDocumentIds);
    setInspectedDocumentId(nextInspectedDocumentId);
    setOpenFolderPaths(Array.isArray(stored?.openFolderPaths) ? stored.openFolderPaths : allFolderTree.map((folder) => folder.path));
    hydratedStateKeyRef.current = storageKey;
  }, [allFolderTree, documents, organizationId]);

  useEffect(() => {
    if (hydratedStateKeyRef.current !== getReportsPageStateStorageKey(organizationId)) {
      return;
    }
    writeReportsPageState(organizationId, {
      title,
      reportType,
      selectedDocumentIds,
      inspectedDocumentId,
      openFolderPaths,
    });
  }, [inspectedDocumentId, openFolderPaths, organizationId, reportType, selectedDocumentIds, title]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setSelectionRailProgress((current) => {
        const delta = selectionRailTarget - current;
        if (Math.abs(delta) < 0.8) {
          window.clearInterval(intervalId);
          return selectionRailTarget;
        }
        return current + Math.sign(delta) * Math.max(0.8, Math.abs(delta) * 0.16);
      });
    }, 140);
    return () => window.clearInterval(intervalId);
  }, [selectionRailTarget]);

  useEffect(() => {
    setStageEtaSecondsRemaining(currentStageEtaTarget);
    if (!showEstimateWorkflowGraph || currentStageEtaTarget <= 0 || currentEstimateStage?.status === "blocked") {
      return;
    }
    const intervalId = window.setInterval(() => {
      setStageEtaSecondsRemaining((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [currentEstimateStage?.id, currentEstimateStage?.status, currentStageEtaTarget, showEstimateWorkflowGraph]);

  useEffect(() => {
    setCurrentWorkTick(0);
    if (
      !showEstimateWorkflowGraph ||
      !activeSpecialReportForType ||
      !currentEstimateStage ||
      ["pending", "completed"].includes(currentEstimateStage.status)
    ) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setCurrentWorkTick((current) => current + 1);
    }, 1250);
    return () => window.clearInterval(intervalId);
  }, [activeSpecialReportForType?.id, currentEstimateStage?.id, currentEstimateStage?.status, showEstimateWorkflowGraph]);

  function getSelectableReportDocuments(folderDocuments: DocumentItem[]) {
    return folderDocuments.filter((document) => ["processed", "requires_review"].includes(document.status));
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((item) => item !== documentId) : [...current, documentId],
    );
  }

  function toggleFolderDocuments(folderDocuments: DocumentItem[]) {
    const selectableDocuments = getSelectableReportDocuments(folderDocuments);
    const folderDocumentIds = selectableDocuments.map((document) => document.id);
    if (folderDocumentIds.length === 0) {
      return;
    }
    setSelectedDocumentIds((current) => {
      const allSelected = folderDocumentIds.every((documentId) => current.includes(documentId));
      if (allSelected) {
        return current.filter((documentId) => !folderDocumentIds.includes(documentId));
      }
      return Array.from(new Set([...current, ...folderDocumentIds]));
    });
  }

  function toggleReportFolderOpen(folderPath: string, isOpen: boolean) {
    setOpenFolderPaths((current) => {
      if (isOpen) {
        return current.includes(folderPath) ? current : [...current, folderPath];
      }
      return current.filter((path) => path !== folderPath);
    });
  }

  function handleReportTypeChange(value: string) {
    setReportType(value);
    setTitle(getReportTypeDefaultTitle(value));
    setSelectedDocumentIds([]);
    setInspectedDocumentId(null);
  }

  function canSubmit(status: string): boolean {
    return ["draft", "requires_review", "in_revision"].includes(status);
  }

  function canApprove(status: string): boolean {
    return status === "awaiting_approval";
  }

  async function handleCreateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }
    await onCreateReport({
      title: title.trim(),
      report_type: reportType,
      selected_document_ids: selectedDocumentIds,
    });
    if (isSpecialEstimateCostReport) {
      setSelectedDocumentIds([]);
      setInspectedDocumentId(null);
      setOpenFolderPaths([]);
      setSelectionRailProgress(0);
    }
  }

  function renderReportActions(report: ReportItem, isSpecialReport: boolean, actionsLocked: boolean) {
    const exportOptions = isSpecialReport ? ESTIMATE_EXPORT_OPTIONS : EXPORT_OPTIONS;
    const lockedButtonClass = actionsLocked ? "action-button action-light report-action-locked" : "";
    return (
      <div className="report-local-toolbar">
        <div>
          <span className="eyebrow">Действия отчета</span>
          <strong>{isSpecialReport ? "Спецworkflow" : "Обычный отчет"}</strong>
          <p>
            {actionsLocked
              ? "Итоговый отчет еще формируется. Действия станут доступны после прохождения всех этапов проверки."
              : isSpecialReport
              ? "Проверка идет через последовательные этапы ниже. Общие действия применяются ко всему отчету."
              : "Общие действия применяются ко всему выбранному отчету."}
          </p>
        </div>
        <div className="report-local-actions">
          {!isSpecialReport ? (
            <>
              <button type="button" className="action-button action-primary" onClick={() => onAnalyze(report.id)}>
                Анализ
              </button>
              <button type="button" className="action-button action-secondary" onClick={() => onGenerate(report.id)}>
                Генерация
              </button>
              <button
                type="button"
                className="action-button action-ghost"
                disabled={!canSubmit(report.status)}
                onClick={() => onSubmitForApproval(report.id)}
              >
                На согласование
              </button>
            </>
          ) : null}
          <div className="inline-menu-anchor">
            <button
              type="button"
              className="action-button action-light"
              disabled={actionsLocked}
              onClick={() => setExportMenuReportId((current) => (current === report.id ? null : report.id))}
            >
              Скачать
            </button>
            {exportMenuReportId === report.id && !actionsLocked ? (
              <div className="inline-menu">
                {exportOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className="inline-menu-item"
                    onClick={() => {
                      setExportMenuReportId(null);
                      void onExport(report.id, option.value);
                    }}
                  >
                    <strong>{option.label}</strong>
                    <span>{option.hint}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            className={actionsLocked ? lockedButtonClass : "action-button action-success"}
            disabled={actionsLocked || !canApprove(report.status)}
            onClick={() => onApprove(report.id)}
          >
            Согласовать
          </button>
          <button
            type="button"
            className={actionsLocked ? lockedButtonClass : "action-button action-warning"}
            disabled={actionsLocked || !canApprove(report.status)}
            onClick={() => onReturnToRevision(report.id)}
          >
            На доработку
          </button>
          <button type="button" className="action-button action-danger" onClick={() => void onDeleteReport(report)}>
            Удалить
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <PageGuide
        title="Отчеты"
        summary="Здесь пользователь собирает рабочий пакет отчета: выбирает документы, создает карточку отчета, запускает анализ, затем генерирует текст разделов, экспортирует результат и переводит отчет в согласование."
        blocks={[
          {
            title: "Что сюда подается",
            points: [
              "Выбранные обработанные документы из раздела «Документы».",
              "Можно выбрать отдельные файлы или сразу всю папку/ветку документов.",
              "Для государственной экспертизы по сметной стоимости выбирается папка с уже обработанным комплектом.",
              "Тип отчета и его название.",
              "Решение пользователя: запустить анализ, генерацию или экспорт.",
            ],
          },
          {
            title: "Что отсюда получает пользователь",
            points: [
              "Статус отчета и показатель готовности.",
              "Переход к требованиям, матрице, рискам и XAI-объяснениям после обычного анализа.",
              "Для отчета по достоверности сметной стоимости — подготовка отдельного workflow проверки.",
              "Экспорт через единое меню скачивания вместо набора разрозненных кнопок.",
            ],
          },
          {
            title: "Как работать эффективнее",
            points: [
              "Не включай в отчет лишние документы: лучше собрать осмысленный пакет под конкретную проверку.",
              "Если документы загружены папкой, выбирай ветку целиком: анализ пойдет по всем обработанным файлам этой папки.",
              "После анализа сначала проверь требования и матрицу, а уже потом запускай генерацию текста.",
              "На согласование отправляй только после проверки рисков, матрицы и XAI-объяснений.",
            ],
          },
        ]}
      />
      <section className="panel">
        <div className="section-header">
          <h2>Новый отчет</h2>
        </div>
        <p className="helper-text">
          Для создания отчета выбери пакет документов. Лучше включать только те источники, которые реально нужны для
          текущего проверочного сценария.
        </p>
        <form className="form-grid" onSubmit={handleCreateReport}>
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Название отчета" />
          <select value={reportType} onChange={(event) => handleReportTypeChange(event.target.value)}>
            {REPORT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {showEstimateWorkflowGraph ? (
            <section className="estimate-workflow-preview field-span-2">
              <div className="estimate-special-summary">
                <div>
                  <p className="eyebrow">Специализированный workflow</p>
                  <h3>Проверка достоверности определения сметной стоимости</h3>
                  <p>
                    Этот тип отчета не запускает обычный анализ требований. Он резервирует отдельный маршрут проверки:
                    соответствие названия содержанию, {estimateRegulationLabel === "ПП РФ N 145" ? `комплектность по ${estimateRegulationLabel}, ` : `содержание разделов по ${estimateRegulationLabel}, `}
                  качество документов, подписи, печати, орфография и XAI по каждому выводу.
                  {displayEstimateReportType === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87
                    ? " Этап комплектности для ПП 87 не используется."
                    : ""}
                </p>
                </div>
                <div className={`estimate-eta-card ${currentEstimateStage?.status === "blocked" ? "waiting" : ""}`}>
                  <span>Таймер текущего этапа</span>
                  <strong>{currentStageEtaLabel}</strong>
                  <p>Этап: {currentEstimateStage?.shortTitle ?? "ожидает"}</p>
                  <p>
                    Файлы этапа: {visualCurrentStageCheckedFiles}/{currentStageTotalFiles}
                  </p>
                </div>
              </div>

              <section className="estimate-selection-panel">
                <div className="section-header">
                  <h3>Единая шкала проверки выбранного пакета</h3>
                  <span>Этап: {currentEstimateStage?.shortTitle ?? "ожидает"}</span>
                </div>
                <p className="helper-text">
                  Это общий график этапов для выбранного типа отчета. Кружок этапа закрашивается только после полного
                  завершения этапа; во время работы линия доходит до текущего этапа, но не закрашивает его.
                </p>
                <div className="estimate-stage-rail compact-rail">
                  <div className="estimate-stage-rail-base" />
                  <div className="estimate-stage-rail-fill" style={{ width: `${selectionRailProgress}%` }} />
                  <div className="estimate-stage-nodes">
                    {estimateRailStages.map((stage) => {
                      const stageTotalFiles = stage.totalFiles || totalWorkflowFiles;
                      const stageCheckedFiles =
                        stage.id === currentEstimateStage?.id ? visualCurrentStageCheckedFiles : stage.totalFiles ? stage.checkedFiles : 0;
                      return (
                        <article key={stage.id} className={`estimate-stage-node ${stage.status}`}>
                          <span>{stage.order}</span>
                          <strong>{stage.shortTitle}</strong>
                          <small>{STAGE_STATUS_LABELS[stage.status]}</small>
                          <small>
                            Файлы: {stageCheckedFiles}/{stageTotalFiles}
                          </small>
                        </article>
                      );
                    })}
                  </div>
                </div>
                <div className="folder-summary-grid">
                  <span>Выбрано: {selectedSummary.total}</span>
                  <span>
                    Полностью готовы: {fullyReadyFilesCount}/{totalWorkflowFiles}
                  </span>
                  <span>Текущий этап: {currentEstimateStage?.shortTitle ?? "ожидает"}</span>
                  <span>
                    Файлы текущего этапа: {visualCurrentStageCheckedFiles}/{currentStageTotalFiles}
                  </span>
                </div>
                <div className="estimate-current-work">
                  <div className="section-header compact-header">
                    <h3>{activeSpecialReportForType ? "Файлы текущего этапа" : "Файлы будут проверяться после запуска"}</h3>
                    <span>{activeWorkflowSourceDocuments.length}</span>
                  </div>
                  {currentStageWorkItems.length > 0 ? (
                    <div className="estimate-current-work-list">
                      {currentStageWorkItems.map((item) => (
                        <article key={`${item.name}-${item.detail}`} className={`estimate-current-work-item tone-${item.tone}`}>
                          <div>
                            <strong>{item.name}</strong>
                            <span>{item.detail}</span>
                          </div>
                          <div className="mini-progress-track">
                            <div className={`progress-fill tone-${item.tone}`} style={{ width: `${item.progress}%` }} />
                          </div>
                          <small>{Math.round(item.progress)}%</small>
                        </article>
                      ))}
                      {hiddenWorkItemsCount > 0 ? (
                        <p className="helper-text">Еще {hiddenWorkItemsCount} файл(ов) участвуют в текущем маршруте.</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="helper-text">
                      Выберите папку с обработанными файлами. После нажатия `Создать спецотчет` здесь появится текущий
                      файл или группа файлов этапа.
                    </p>
                  )}
                </div>
              </section>

              <div className="estimate-folder-note">
                <strong>Выбор источника для workflow</strong>
                <p>
                  Ниже показана вся структура папок организации. В спецотчет попадут только файлы со статусом
                  «обработан» или «нужна проверка», а неготовые файлы останутся видимыми как причина желтого или
                  красного статуса папки.
                </p>
              </div>
            </section>
          ) : null}

          <section className="field-span-2">
            <div className="section-header compact-header">
              <h3>Выбор папок и файлов для отчета</h3>
              <span>{processedDocuments.length} доступно к выбору</span>
            </div>
            <p className="helper-text">
              Сначала показаны сводки по папкам. Откройте папку, чтобы выбрать файл; справа появятся ошибки обработки и
              замечания модели по этому источнику.
            </p>
            <div className={`report-folder-workspace ${inspectedDocument ? "with-inspector" : ""}`}>
              <DocumentFolderTree
                folders={allFolderTree}
                mode="select"
                defaultOpen={false}
                activeDocumentId={inspectedDocumentId}
                selectedDocumentIds={selectedDocumentIds}
                openFolderPaths={openFolderPaths}
                getSelectableDocuments={getSelectableReportDocuments}
                onInspectDocument={(document) => setInspectedDocumentId(document.id)}
                onToggleDocument={toggleDocument}
                onToggleFolder={toggleFolderDocuments}
                onToggleFolderOpen={toggleReportFolderOpen}
              />
              {inspectedDocument ? (
                <aside className="document-issues-panel">
                  <div className="section-header compact-header">
                    <h3>Ошибки выбранного файла</h3>
                    <span>{inspectedDocument.status}</span>
                  </div>
                  <div className="document-issues-head">
                    <strong>{inspectedDocument.file_name}</strong>
                    {inspectedDocument.relative_path ? <p>{inspectedDocument.relative_path}</p> : null}
                  </div>
                  <div className="document-issues-list">
                    {inspectedIssues.map((issue) => (
                      <article key={`${issue.title}-${issue.detail}`} className={`document-issue-item tone-${issue.tone}`}>
                        <strong>{issue.title}</strong>
                        <p>{issue.detail}</p>
                      </article>
                    ))}
                  </div>
                </aside>
              ) : null}
            </div>
          </section>
          {isSpecialEstimateCostReport && hasBlockingSpecialWorkflowForType ? (
            <div className="field-span-2 estimate-active-workflow-lock">
              <strong>Спецотчет уже запущен</strong>
              <p>
                Для типа «{formatReportType(reportType)}» сейчас активен отчет «{activeSpecialReportForType?.title}».
                Завершите решения по нему или выберите другой тип отчета.
              </p>
              {activeSpecialReportForType ? (
                <button type="button" className="action-button action-light" onClick={() => onSelectReport(activeSpecialReportForType.id)}>
                  Открыть активный отчет
                </button>
              ) : null}
            </div>
          ) : (
            <button type="submit" disabled={selectedDocumentIds.length === 0}>
              {isSpecialEstimateCostReport ? "Создать спецотчет" : "Создать отчет"}
            </button>
          )}
          {!isSpecialEstimateCostReport ? (
            <button
              type="button"
              className="action-button action-primary"
              disabled={!title.trim() || selectedDocumentIds.length === 0}
              onClick={() =>
                void onCreateAndAnalyzeReport({
                  title: title.trim(),
                  report_type: reportType,
                  selected_document_ids: selectedDocumentIds,
                })
              }
            >
              Создать и анализировать
            </button>
          ) : null}
        </form>
      </section>

      {reviewSpecialReport && reviewSpecialWorkflow ? (
        <section className="panel estimate-review-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Проверка файлов и решений пользователя</p>
              <h2>Замечания спецотчета</h2>
            </div>
            <span>{formatReportType(reviewSpecialReport.report_type)}</span>
          </div>
          <p className="helper-text">
            Здесь отображаются только выводы текущего спецworkflow: какие файлы требуют проверки, какое действие нужно
            выполнить и какое XAI-объяснение стоит за выводом. Список отчетов ниже остается реестром карточек.
          </p>
          <EstimateWorkflowPanel
            reportId={reviewSpecialReport.id}
            workflow={reviewSpecialWorkflow}
            onWorkflowUpdate={(workflow) => onEstimateWorkflowUpdate(reviewSpecialReport.id, workflow)}
          />
        </section>
      ) : null}

      <section className="panel">
        <div className="section-header">
          <h2>Отчеты</h2>
          <span>{reports.length}</span>
        </div>
        <p className="helper-text">
          Анализ формирует требования, матрицу и XAI-объяснения. Генерация создает черновик отчета и данные для
          экспорта. Риски появляются только если система нашла пробелы или несоответствия.
        </p>
        <div className="list">
          {reports.map((report) => {
            const isSelected = selectedReportId === report.id;
            const isSpecialReport = isStateExpertiseEstimateCostReport(report.report_type);
            const reportWorkflow = isSpecialReport ? getWorkflowForReport(report, documents, estimateWorkflowByReportId) : null;
            const isSpecialReportReady = isSpecialReport ? isWorkflowComplete(reportWorkflow) : true;
            const actionsLocked = isSpecialReport && !isSpecialReportReady;
            const liveReadinessPercent =
              isSpecialReport && reportWorkflow
                ? isSpecialReportReady
                  ? 100
                  : reportWorkflow.progress
                : report.status === "analyzing"
                ? getLiveReportAnalysisProgress(report.readiness_percent, getReportElapsedMs(report))
                : report.readiness_percent;
            const readiness = getReadinessMeta(liveReadinessPercent);
            return (
              <article key={report.id} className={`list-item report-card tone-${readiness.tone} ${actionsLocked ? "is-forming" : ""} ${isSelected ? "selected-row" : ""}`}>
                <div className="report-card-main">
                  <div className="report-card-head">
                    <button
                      type="button"
                      className={`selection-indicator report-selector ${isSelected ? "active" : ""}`}
                      onClick={() => onSelectReport(report.id)}
                      aria-label={`Выбрать отчет ${report.title}`}
                    >
                      {isSelected ? "✓" : ""}
                    </button>
                    <div>
                      <strong>{report.title}</strong>
                      <p>
                        {formatReportType(report.report_type)} · {formatReportStatus(report.status)}
                      </p>
                    </div>
                  </div>
                  {isSelected ? renderReportActions(report, isSpecialReport, actionsLocked) : null}
                  <div className="status-meter">
                    <div className="meter-meta">
                      <span>{actionsLocked ? "Формируется" : readiness.label}</span>
                      <strong>{Math.round(liveReadinessPercent)}%</strong>
                    </div>
                    <div className="progress-track">
                      <div
                        className={`progress-fill tone-${readiness.tone} ${actionsLocked ? "animated-fill" : ""}`}
                        style={{ width: `${readiness.progress}%` }}
                      />
                    </div>
                    <p className="helper-text">
                      {actionsLocked
                        ? `Итоговый отчет формируется. Проверено файлов: ${reportWorkflow?.checkedFiles ?? 0}/${reportWorkflow?.totalFiles ?? 0}. Действия станут доступны после финальной готовности.`
                        : null}
                      {!actionsLocked && report.status === "draft" ? "Отчет создан, но анализ еще не запущен." : null}
                      {!actionsLocked && report.status === "analyzing" ? "Система сейчас извлекает требования, evidence и XAI." : null}
                      {!actionsLocked && report.status === "requires_review" ? "Анализ завершен, теперь проверь требования, матрицу и риски." : null}
                      {!actionsLocked && report.status === "awaiting_approval" ? "Отчет отправлен на согласование." : null}
                      {!actionsLocked && report.status === "approved" ? "Отчет согласован и готов к финальной выгрузке." : null}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
