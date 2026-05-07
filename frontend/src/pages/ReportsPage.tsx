import { FormEvent, useState } from "react";

import type { DocumentItem, ReportItem } from "../lib/types";

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
      <section className="panel">
        <div className="section-header">
          <h2>Новый отчет</h2>
        </div>
        <form className="form-grid" onSubmit={handleCreateReport}>
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Название отчета" />
          <select value={reportType} onChange={(event) => setReportType(event.target.value)}>
            <option value="readiness_report">Готовность к проверке</option>
            <option value="template_report">Отчет по шаблону</option>
            <option value="document_completeness">Комплектность документов</option>
          </select>
          <div className="checkbox-grid">
            {documents.map((document) => (
              <label key={document.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selectedDocumentIds.includes(document.id)}
                  onChange={() => toggleDocument(document.id)}
                />
                <span>{document.file_name}</span>
              </label>
            ))}
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
          {reports.map((report) => (
            <article key={report.id} className="list-item">
              <div>
                <strong>{report.title}</strong>
                <p>
                  {report.report_type} · {report.status}
                </p>
              </div>
              <div className="report-actions">
                <span>{report.readiness_percent}%</span>
                <button type="button" onClick={() => onSelectReport(report.id)}>
                  {selectedReportId === report.id ? "Выбран" : "Открыть"}
                </button>
                <button type="button" onClick={() => onAnalyze(report.id)}>
                  Анализ
                </button>
                <button type="button" onClick={() => onGenerate(report.id)}>
                  Генерация
                </button>
                <button type="button" onClick={() => onExport(report.id, "docx")}>
                  DOCX
                </button>
                <button type="button" onClick={() => onExport(report.id, "matrix")}>
                  XLSX
                </button>
                <button type="button" onClick={() => onExport(report.id, "package")}>
                  ZIP
                </button>
                <button type="button" onClick={() => onExport(report.id, "explanations")}>
                  XAI HTML
                </button>
                <button type="button" disabled={!canSubmit(report.status)} onClick={() => onSubmitForApproval(report.id)}>
                  На согласование
                </button>
                <button type="button" disabled={!canApprove(report.status)} onClick={() => onApprove(report.id)}>
                  Согласовать
                </button>
                <button type="button" disabled={!canApprove(report.status)} onClick={() => onReturnToRevision(report.id)}>
                  На доработку
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
