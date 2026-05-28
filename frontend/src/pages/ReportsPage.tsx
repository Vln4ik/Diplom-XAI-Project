import { FormEvent, useEffect, useMemo, useState } from "react";

import { DocumentFolderTree } from "../components/DocumentFolderTree";
import { EstimateWorkflowPanel } from "../components/EstimateWorkflowPanel";
import { PageGuide } from "../components/PageGuide";
import {
  buildDocumentFolderTree,
  summarizeFolderDocuments,
} from "../lib/documentTree";
import { buildEstimateExpertiseWorkflow } from "../lib/estimateExpertise";
import { useLiveReportProgress } from "../lib/liveProgress";
import {
  getStateExpertiseRegulationLabel,
  getReportTypeDefaultTitle,
  isStateExpertiseEstimateCostReport,
  REPORT_TYPE_OPTIONS,
} from "../lib/reportTypes";
import type { DocumentItem, ReportItem } from "../lib/types";
import {
  formatReportStatus,
  formatReportType,
  getLiveReportAnalysisProgress,
  getReadinessMeta,
} from "../lib/ui";

type Props = {
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
};

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
  if (regulationLabel === "ПП РФ N 145") {
    baseStages.push(`Комплектность по ${regulationLabel}`);
  } else {
    baseStages.push(`Содержание разделов по ${regulationLabel}`);
  }
  return [...baseStages, "Лексика, орфография, подписи", "Финальная готовность"];
}

function estimateSelectionEtaSeconds(selectedDocuments: DocumentItem[], summary: ReturnType<typeof summarizeFolderDocuments>): number {
  if (selectedDocuments.length === 0) {
    return 0;
  }
  const baseSeconds = 180;
  const perDocumentSeconds = selectedDocuments.length * 55;
  const pendingPenalty = summary.pending * 70;
  const failedPenalty = summary.failed * 90;
  return Math.max(90, baseSeconds + perDocumentSeconds + pendingPenalty + failedPenalty);
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
}: Props) {
  const [title, setTitle] = useState("Отчет о готовности к проверке");
  const [reportType, setReportType] = useState("readiness_report");
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [exportMenuReportId, setExportMenuReportId] = useState<string | null>(null);
  const [selectionRailProgress, setSelectionRailProgress] = useState(0);
  const [etaSecondsRemaining, setEtaSecondsRemaining] = useState(0);
  const [inspectedDocumentId, setInspectedDocumentId] = useState<string | null>(null);
  const isSpecialEstimateCostReport = isStateExpertiseEstimateCostReport(reportType);
  const estimateRegulationLabel = getStateExpertiseRegulationLabel(reportType);
  const estimateCostStages = getEstimateCostStages(reportType);
  const hasSpecialEstimateReport = reports.some((report) => report.report_type === reportType);
  const { getReportElapsedMs } = useLiveReportProgress(reports);

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
  const selectedSummary = summarizeFolderDocuments(selectedDocuments);
  const selectionRailTarget = selectedDocuments.length === 0 ? 8 : Math.min(36, 16 + selectedSummary.averageProgress * 0.2);
  const estimatedEtaTarget = estimateSelectionEtaSeconds(selectedDocuments, selectedSummary);
  const inspectedIssues = getDocumentIssueItems(inspectedDocument);

  useEffect(() => {
    setSelectionRailProgress(0);
    const animationId = window.requestAnimationFrame(() => {
      setSelectionRailProgress(selectionRailTarget);
    });
    return () => window.cancelAnimationFrame(animationId);
  }, [selectionRailTarget]);

  useEffect(() => {
    setEtaSecondsRemaining(estimatedEtaTarget);
    if (!isSpecialEstimateCostReport || estimatedEtaTarget <= 0) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setEtaSecondsRemaining((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [estimatedEtaTarget, isSpecialEstimateCostReport]);

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
      setInspectedDocumentId(null);
    }
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
          {isSpecialEstimateCostReport && !hasSpecialEstimateReport ? (
            <section className="estimate-workflow-preview field-span-2">
              <div>
                <p className="eyebrow">Специализированный workflow</p>
                <h3>Проверка достоверности определения сметной стоимости</h3>
                <p>
                  Этот тип отчета не запускает обычный анализ требований. Он резервирует отдельный маршрут проверки:
                  соответствие названия содержанию, {estimateRegulationLabel === "ПП РФ N 145" ? `комплектность по ${estimateRegulationLabel}, ` : `содержание разделов по ${estimateRegulationLabel}, `}
                  качество документов, подписи, печати, орфография и XAI по каждому выводу.
                </p>
              </div>
              <div className="estimate-stage-preview">
                {estimateCostStages.map((stage, index) => (
                  <article key={stage} className={index === 0 ? "active" : ""}>
                    <span>{index + 1}</span>
                    <strong>{stage}</strong>
                  </article>
                ))}
              </div>
              <div className="estimate-folder-note">
                <strong>Выбор источника для Phase 2</strong>
                <p>
                  Ниже показана вся структура папок организации. В спецотчет попадут только файлы со статусом
                  «обработан» или «нужна проверка», а неготовые файлы останутся видимыми как причина желтого или
                  красного статуса папки.
                </p>
              </div>
            </section>
          ) : null}
          {isSpecialEstimateCostReport && selectedDocuments.length > 0 ? (
            <section className="estimate-selection-panel field-span-2">
              <div className="section-header">
                <h3>Общая шкала проверки выбранного пакета</h3>
                <span>{selectedDocuments.length} файл(ов) · осталось: {formatRealtimeEta(etaSecondsRemaining)}</span>
              </div>
              <p className="helper-text">
                Это единая интерактивная шкала для всех выбранных папок и файлов. После создания спецотчета она будет
                заменена backend workflow с реальными этапами, findings и XAI.
              </p>
              <div className="estimate-stage-rail compact-rail">
                <div className="estimate-stage-rail-base" />
                <div className="estimate-stage-rail-fill" style={{ width: `${selectionRailProgress}%` }} />
                <div className="estimate-stage-nodes">
                  {estimateCostStages.map((stage, index) => {
                    const statusClass =
                      selectedDocuments.length === 0
                        ? index === 0
                          ? "running"
                          : "pending"
                        : index === 0
                          ? "completed"
                          : index === 1
                            ? "running"
                            : "pending";
                    return (
                      <article key={stage} className={`estimate-stage-node ${statusClass}`}>
                        <span>{index + 1}</span>
                        <strong>{stage}</strong>
                        <small>
                          {index === 0 && selectedDocuments.length > 0
                            ? "пакет выбран"
                            : index === 1 && selectedDocuments.length > 0
                              ? "следующий этап"
                              : "ожидает"}
                        </small>
                      </article>
                    );
                  })}
                </div>
              </div>
              <div className="folder-summary-grid">
                <span>Выбрано: {selectedSummary.total}</span>
                <span>Готовы: {selectedSummary.ready}</span>
                <span>Не готовы: {selectedSummary.pending}</span>
                <span>Ошибки: {selectedSummary.failed}</span>
              </div>
            </section>
          ) : null}

          <section className="field-span-2">
            <div className="section-header compact-header">
              <h3>Выбор папок и файлов для отчета</h3>
              <span>{processedDocuments.length} готово</span>
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
                sortByHealth
                activeDocumentId={inspectedDocumentId}
                selectedDocumentIds={selectedDocumentIds}
                getSelectableDocuments={getSelectableReportDocuments}
                onInspectDocument={(document) => setInspectedDocumentId(document.id)}
                onToggleDocument={toggleDocument}
                onToggleFolder={toggleFolderDocuments}
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
          <button type="submit" disabled={selectedDocumentIds.length === 0}>
            {isSpecialEstimateCostReport ? "Создать спецотчет" : "Создать отчет"}
          </button>
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
            const estimateWorkflow = isSpecialReport ? buildEstimateExpertiseWorkflow(report, documents) : null;
            const liveReadinessPercent =
              report.status === "analyzing"
                ? getLiveReportAnalysisProgress(report.readiness_percent, getReportElapsedMs(report))
                : report.readiness_percent;
            const readiness = getReadinessMeta(liveReadinessPercent);
            return (
              <article key={report.id} className={`list-item report-card tone-${readiness.tone} ${isSelected ? "selected-row" : ""}`}>
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
                  <div className="status-meter">
                    <div className="meter-meta">
                      <span>{readiness.label}</span>
                      <strong>{Math.round(liveReadinessPercent)}%</strong>
                    </div>
                    <div className="progress-track">
                      <div className={`progress-fill tone-${readiness.tone}`} style={{ width: `${readiness.progress}%` }} />
                    </div>
                    <p className="helper-text">
                      {report.status === "draft" ? "Отчет создан, но анализ еще не запущен." : null}
                      {report.status === "analyzing" ? "Система сейчас извлекает требования, evidence и XAI." : null}
                      {report.status === "requires_review" ? "Анализ завершен, теперь проверь требования, матрицу и риски." : null}
                      {report.status === "awaiting_approval" ? "Отчет отправлен на согласование." : null}
                      {report.status === "approved" ? "Отчет согласован и готов к финальной выгрузке." : null}
                    </p>
                  </div>
                  {estimateWorkflow ? <EstimateWorkflowPanel reportId={report.id} workflow={estimateWorkflow} /> : null}
                </div>
                <div className="report-action-stack">
                  {isSpecialReport ? (
                    <div className="estimate-report-actions">
                      <span className="status-pill tone-info">Спецworkflow</span>
                      <p>
                        Обычный анализ и генерация отключены. Ниже уже доступен демонстрационный маршрут
                        государственной экспертизы по сметной стоимости.
                      </p>
                      <button type="button" className="action-button action-secondary" disabled>
                        Workflow: UI skeleton
                      </button>
                    </div>
                  ) : (
                    <div className="action-cluster">
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
                    </div>
                  )}
                  <div className="action-cluster">
                    <div className="inline-menu-anchor">
                      <button
                        type="button"
                        className="action-button action-light"
                        onClick={() => setExportMenuReportId((current) => (current === report.id ? null : report.id))}
                      >
                        Скачать
                      </button>
                      {exportMenuReportId === report.id ? (
                        <div className="inline-menu">
                          {(isStateExpertiseEstimateCostReport(report.report_type) ? ESTIMATE_EXPORT_OPTIONS : EXPORT_OPTIONS).map((option) => (
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
                      className="action-button action-success"
                      disabled={!canApprove(report.status)}
                      onClick={() => onApprove(report.id)}
                    >
                      Согласовать
                    </button>
                    <button
                      type="button"
                      className="action-button action-warning"
                      disabled={!canApprove(report.status)}
                      onClick={() => onReturnToRevision(report.id)}
                    >
                      На доработку
                    </button>
                    <button type="button" className="action-button action-danger" onClick={() => void onDeleteReport(report)}>
                      Удалить
                    </button>
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
