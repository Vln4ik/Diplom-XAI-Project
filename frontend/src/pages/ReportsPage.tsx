import { FormEvent, useMemo, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import type { DocumentItem, ReportItem } from "../lib/types";
import {
  formatDocumentStatus,
  formatReportStatus,
  formatReportType,
  getReadinessMeta,
} from "../lib/ui";

type Props = {
  reports: ReportItem[];
  documents: DocumentItem[];
  selectedReportId: string | null;
  onSelectReport: (reportId: string) => void;
  onCreateReport: (payload: { title: string; report_type: string; selected_document_ids: string[] }) => Promise<void>;
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

export function ReportsPage({
  reports,
  documents,
  selectedReportId,
  onSelectReport,
  onCreateReport,
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

  const processedDocuments = useMemo(
    () => documents.filter((document) => ["processed", "requires_review"].includes(document.status)),
    [documents],
  );

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((item) => item !== documentId) : [...current, documentId],
    );
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
              "Тип отчета и его название.",
              "Решение пользователя: запустить анализ, генерацию или экспорт.",
            ],
          },
          {
            title: "Что отсюда получает пользователь",
            points: [
              "Статус отчета и показатель готовности.",
              "Переход к требованиям, матрице, рискам и редактору после анализа.",
              "Экспорт через единое меню скачивания вместо набора разрозненных кнопок.",
            ],
          },
          {
            title: "Как работать эффективнее",
            points: [
              "Не включай в отчет лишние документы: лучше собрать осмысленный пакет под конкретную проверку.",
              "После анализа сначала проверь требования и матрицу, а уже потом запускай генерацию текста.",
              "На согласование отправляй только после проверки рисков и редактора отчета.",
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
          <select value={reportType} onChange={(event) => setReportType(event.target.value)}>
            <option value="readiness_report">Готовность к проверке</option>
            <option value="template_report">Отчет по шаблону</option>
            <option value="document_completeness">Комплектность документов</option>
          </select>
          <div className="selection-grid">
            {processedDocuments.map((document) => {
              const isSelected = selectedDocumentIds.includes(document.id);
              return (
                <button
                  key={document.id}
                  type="button"
                  className={`selection-card ${isSelected ? "active" : ""}`}
                  onClick={() => toggleDocument(document.id)}
                >
                  <span className={`selection-indicator ${isSelected ? "active" : ""}`}>{isSelected ? "✓" : ""}</span>
                  <div>
                    <strong>{document.file_name}</strong>
                    <p>{formatDocumentStatus(document.status)}</p>
                  </div>
                </button>
              );
            })}
          </div>
          <button type="submit">Создать отчет</button>
        </form>
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Отчеты</h2>
          <span>{reports.length}</span>
        </div>
        <p className="helper-text">
          Анализ формирует требования, матрицу и XAI-объяснения. Генерация создает разделы для вкладки
          &quot;Редактор отчета&quot;. Риски появляются только если система нашла пробелы или несоответствия.
        </p>
        <div className="list">
          {reports.map((report) => {
            const isSelected = selectedReportId === report.id;
            const readiness = getReadinessMeta(report.readiness_percent);
            return (
              <article key={report.id} className={`list-item report-card ${isSelected ? "selected-row" : ""}`}>
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
                      <strong>{report.readiness_percent}%</strong>
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
                </div>
                <div className="report-action-stack">
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
                          {EXPORT_OPTIONS.map((option) => (
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
