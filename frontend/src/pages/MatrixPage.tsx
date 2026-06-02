import { useMemo, useState } from "react";

import { DocumentFolderTree } from "../components/DocumentFolderTree";
import { PageGuide } from "../components/PageGuide";
import { buildDocumentFolderTree } from "../lib/documentTree";
import type { AuditLogItem, DocumentItem, ExpertiseDecisionItem, ReportItem, ReportMatrixRow, RequirementItem, RiskItem } from "../lib/types";
import { formatDocumentStatus, formatReportStatus, formatReportType, formatRiskLevel, getScoreTone } from "../lib/ui";

type Props = {
  documents: DocumentItem[];
  reports: ReportItem[];
  rows: ReportMatrixRow[];
  requirements: RequirementItem[];
  risks: RiskItem[];
  expertiseDecisions: ExpertiseDecisionItem[];
  auditLogs: AuditLogItem[];
  selectedRequirementId: string | null;
  onSelectRequirement: (requirementId: string) => void;
};

type GraphNode = {
  id: string;
  label: string;
  meta: string;
  kind: "document" | "report" | "requirement" | "risk" | "decision" | "evidence";
  tone: "success" | "warning" | "danger" | "info";
  x: number;
  y: number;
};

type GraphEdge = {
  id: string;
  from: string;
  to: string;
  tone: "success" | "warning" | "danger" | "info";
};

type HistoryItem = {
  id: string;
  title: string;
  body: string;
  meta: string;
  createdAt: string;
  tone: "success" | "warning" | "danger" | "info";
};

function compactText(value: string, limit = 80): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function getDocumentDisplayName(document: DocumentItem): string {
  return document.relative_path || document.original_file_name || document.file_name;
}

function documentMatchesMatrixRow(document: DocumentItem, row: ReportMatrixRow): boolean {
  const documentNames = [document.file_name, document.original_file_name, document.relative_path].filter(Boolean) as string[];
  return documentNames.some((name) => {
    if (row.source_document_name === name) {
      return true;
    }
    return row.evidence.some((item) => item.document_name === name);
  });
}

function detailsContainDocument(details: unknown, document: DocumentItem): boolean {
  const text = JSON.stringify(details ?? {}).toLowerCase();
  return [document.id, document.file_name, document.original_file_name, document.relative_path]
    .filter(Boolean)
    .some((value) => text.includes(String(value).toLowerCase()));
}

function getDocumentTone(document: DocumentItem): GraphNode["tone"] {
  if (document.status === "processed") {
    return "success";
  }
  if (document.status === "failed") {
    return "danger";
  }
  if (["requires_review", "queued", "processing"].includes(document.status)) {
    return "warning";
  }
  return "info";
}

function getRiskToneStrict(level: string): GraphNode["tone"] {
  return level === "low" ? "success" : level === "medium" ? "warning" : "danger";
}

function getDecisionTone(decision: ExpertiseDecisionItem): GraphNode["tone"] {
  return decision.decision_status === "approved" ? "success" : decision.decision_status === "skipped" ? "warning" : "info";
}

function buildDocumentGraph(params: {
  document: DocumentItem;
  reports: ReportItem[];
  rows: ReportMatrixRow[];
  requirements: RequirementItem[];
  risks: RiskItem[];
  decisions: ExpertiseDecisionItem[];
}): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const { document, reports, rows, requirements, risks, decisions } = params;
  const linkedReports = reports.filter((report) => report.selected_document_ids?.includes(document.id));
  const linkedRows = rows.filter((row) => documentMatchesMatrixRow(document, row));
  const linkedRequirementIds = new Set(linkedRows.map((row) => row.requirement_id));
  const linkedRequirements = requirements.filter((requirement) => linkedRequirementIds.has(requirement.id));
  const linkedRisks = risks.filter((risk) => risk.requirement_id && linkedRequirementIds.has(risk.requirement_id));
  const linkedDecisions = decisions.filter(
    (decision) => decision.document_id === document.id || decision.document_name === document.file_name || decision.document_name === document.original_file_name,
  );

  const nodes: GraphNode[] = [
    {
      id: "document",
      label: compactText(document.file_name, 36),
      meta: formatDocumentStatus(document.status),
      kind: "document",
      tone: getDocumentTone(document),
      x: 50,
      y: 50,
    },
  ];
  const edges: GraphEdge[] = [];

  linkedReports.slice(0, 4).forEach((report, index) => {
    const nodeId = `report-${report.id}`;
    nodes.push({
      id: nodeId,
      label: compactText(report.title, 34),
      meta: `${formatReportType(report.report_type)} · ${Math.round(report.readiness_percent)}%`,
      kind: "report",
      tone: report.readiness_percent >= 95 ? "success" : report.readiness_percent >= 60 ? "warning" : "info",
      x: 18 + index * 16,
      y: index % 2 === 0 ? 18 : 82,
    });
    edges.push({ id: `document-${nodeId}`, from: "document", to: nodeId, tone: "info" });
  });

  linkedRows.slice(0, 5).forEach((row, index) => {
    const nodeId = `requirement-${row.requirement_id}`;
    const confidence = Math.round(row.confidence_score * 100);
    nodes.push({
      id: nodeId,
      label: compactText(row.title, 34),
      meta: `Confidence ${confidence}%`,
      kind: "requirement",
      tone: getScoreTone(confidence),
      x: 72 + (index % 2) * 10,
      y: 18 + index * 13,
    });
    edges.push({ id: `document-${nodeId}`, from: "document", to: nodeId, tone: getScoreTone(confidence) });
  });

  linkedRisks.slice(0, 4).forEach((risk, index) => {
    const nodeId = `risk-${risk.id}`;
    nodes.push({
      id: nodeId,
      label: compactText(risk.title, 32),
      meta: formatRiskLevel(risk.risk_level),
      kind: "risk",
      tone: getRiskToneStrict(risk.risk_level),
      x: 82,
      y: 22 + index * 17,
    });
    edges.push({ id: `document-${nodeId}`, from: "document", to: nodeId, tone: getRiskToneStrict(risk.risk_level) });
  });

  linkedDecisions.slice(0, 4).forEach((decision, index) => {
    const nodeId = `decision-${decision.id}`;
    nodes.push({
      id: nodeId,
      label: compactText(decision.finding_title, 32),
      meta: decision.decision_status === "approved" ? "Одобрено" : decision.decision_status === "skipped" ? "Пропущено" : "Решение",
      kind: "decision",
      tone: getDecisionTone(decision),
      x: 18,
      y: 28 + index * 17,
    });
    edges.push({ id: `document-${nodeId}`, from: "document", to: nodeId, tone: getDecisionTone(decision) });
  });

  if (linkedRows.length > 0) {
    nodes.push({
      id: "evidence",
      label: "Evidence",
      meta: `${linkedRows.length} связей`,
      kind: "evidence",
      tone: "info",
      x: 50,
      y: 15,
    });
    edges.push({ id: "document-evidence", from: "document", to: "evidence", tone: "info" });
  }

  return { nodes, edges };
}

function buildHistory(params: {
  document: DocumentItem;
  reports: ReportItem[];
  rows: ReportMatrixRow[];
  decisions: ExpertiseDecisionItem[];
  auditLogs: AuditLogItem[];
}): HistoryItem[] {
  const { document, reports, rows, decisions, auditLogs } = params;
  const items: HistoryItem[] = [
    {
      id: "created",
      title: "Документ загружен в EvidenceXAI",
      body: getDocumentDisplayName(document),
      meta: "document.created_at",
      createdAt: document.created_at,
      tone: "info",
    },
  ];

  if (document.processed_at) {
    items.push({
      id: "processed",
      title: "Pipeline обработки завершен",
      body: `Финальный статус: ${formatDocumentStatus(document.status)}.`,
      meta: "document.processed_at",
      createdAt: document.processed_at,
      tone: getDocumentTone(document),
    });
  }

  if (document.processing_error) {
    items.push({
      id: "processing-error",
      title: "Зафиксирована причина ручной проверки",
      body: document.processing_error,
      meta: "processing_error",
      createdAt: document.processed_at ?? document.created_at,
      tone: "warning",
    });
  }

  reports
    .filter((report) => report.selected_document_ids?.includes(document.id))
    .forEach((report) => {
      items.push({
        id: `report-${report.id}`,
        title: "Документ включен в отчет",
        body: `${report.title} · ${formatReportType(report.report_type)} · ${formatReportStatus(report.status)}.`,
        meta: `Готовность отчета ${Math.round(report.readiness_percent)}%`,
        createdAt: report.created_at,
        tone: report.readiness_percent >= 95 ? "success" : "info",
      });
    });

  rows
    .filter((row) => documentMatchesMatrixRow(document, row))
    .forEach((row) => {
      const confidence = Math.round(row.confidence_score * 100);
      items.push({
        id: `matrix-${row.requirement_id}`,
        title: "Документ использован как evidence",
        body: `${row.title}. ${row.source_fragment_text ?? row.evidence[0]?.fragment_text ?? "Фрагмент не сохранен."}`,
        meta: `Confidence ${confidence}%`,
        createdAt: document.processed_at ?? document.created_at,
        tone: getScoreTone(confidence),
      });
    });

  decisions
    .filter((decision) => decision.document_id === document.id || decision.document_name === document.file_name || decision.document_name === document.original_file_name)
    .forEach((decision) => {
      items.push({
        id: `decision-${decision.id}`,
        title: decision.decision_status === "approved" ? "Пользователь одобрил вывод" : "Пользователь пропустил вывод",
        body: `${decision.finding_title}. ${decision.recommendation}`,
        meta: `${decision.stage_title} · ${decision.normative_basis}`,
        createdAt: decision.created_at,
        tone: getDecisionTone(decision),
      });
    });

  auditLogs
    .filter((log) => log.entity_id === document.id || detailsContainDocument(log.details, document))
    .forEach((log) => {
      items.push({
        id: `audit-${log.id}`,
        title: `Audit: ${log.action}`,
        body: JSON.stringify(log.details ?? {}),
        meta: `${log.entity_type}${log.user_email ? ` · ${log.user_email}` : ""}`,
        createdAt: log.created_at,
        tone: "info",
      });
    });

  return items.sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());
}

export function MatrixPage({
  documents,
  reports,
  rows,
  requirements,
  risks,
  expertiseDecisions,
  auditLogs,
  selectedRequirementId,
  onSelectRequirement,
}: Props) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [documentSearch, setDocumentSearch] = useState("");
  const normalizedSearch = documentSearch.trim().toLowerCase();
  const filteredDocuments = useMemo(
    () =>
      normalizedSearch
        ? documents.filter((document) =>
            [document.file_name, document.original_file_name, document.relative_path]
              .filter(Boolean)
              .some((value) => String(value).toLowerCase().includes(normalizedSearch)),
          )
        : documents,
    [documents, normalizedSearch],
  );
  const filteredFolderTree = useMemo(() => buildDocumentFolderTree(filteredDocuments), [filteredDocuments]);
  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? filteredDocuments[0] ?? documents[0] ?? null,
    [documents, filteredDocuments, selectedDocumentId],
  );
  const graph = useMemo(
    () =>
      selectedDocument
        ? buildDocumentGraph({
            document: selectedDocument,
            reports,
            rows,
            requirements,
            risks,
            decisions: expertiseDecisions,
          })
        : { nodes: [], edges: [] },
    [expertiseDecisions, reports, requirements, risks, rows, selectedDocument],
  );
  const history = useMemo(
    () =>
      selectedDocument
        ? buildHistory({
            document: selectedDocument,
            reports,
            rows,
            decisions: expertiseDecisions,
            auditLogs,
          })
        : [],
    [auditLogs, expertiseDecisions, reports, rows, selectedDocument],
  );
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));

  return (
    <div className="stack">
      <PageGuide
        title="Графы документов"
        summary="Вкладка показывает отчет по каждому документу в формате графа: документ в центре, вокруг него отчеты, требования, evidence, риски, решения пользователя и XAI-связи."
        blocks={[
          {
            title: "Что смотреть",
            points: [
              "Выбери документ слева, чтобы увидеть его граф связей.",
              "Центральный узел — сам документ; связанные узлы показывают отчеты, требования, риски и решения.",
              "Правая колонка показывает всю доступную историю документа из текущей базы и audit log.",
            ],
          },
          {
            title: "Что получать",
            points: [
              "Понимание, где документ использовался и какие выводы он подтвердил.",
              "Быстрый переход от документа к требованию и XAI-контексту.",
              "Историю загрузки, обработки, включения в отчеты и пользовательских решений.",
            ],
          },
          {
            title: "Ограничение",
            points: [
              "История отображает все события, которые уже сохранены системой: document fields, audit log, матрицу, отчеты и решения спецпроверки.",
              "Если старые действия не логировались в audit log, вкладка восстановит их по текущим связям базы.",
            ],
          },
        ]}
      />

      <section className="graphs-workspace">
        <aside className="panel graph-document-list">
          <div className="section-header">
            <h2>Документы</h2>
            <span>{filteredDocuments.length}/{documents.length}</span>
          </div>
          <label className="graph-search">
            <span>Поиск по названию</span>
            <input
              type="search"
              value={documentSearch}
              onChange={(event) => setDocumentSearch(event.target.value)}
              placeholder="Название файла или папки"
            />
          </label>
          {documents.length === 0 ? (
            <p className="helper-text">Сначала загрузите документы на вкладке «Документы».</p>
          ) : filteredDocuments.length === 0 ? (
            <div className="empty-state">По запросу ничего не найдено.</div>
          ) : (
            <DocumentFolderTree
              folders={filteredFolderTree}
              mode="manage"
              defaultOpen={filteredDocuments.length <= 40 || Boolean(normalizedSearch)}
              activeDocumentId={selectedDocument?.id}
              sortByHealth
              onInspectDocument={(document) => setSelectedDocumentId(document.id)}
            />
          )}
        </aside>

        <section className="panel graph-report-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Графовый отчет</p>
              <h2>{selectedDocument ? selectedDocument.file_name : "Документ не выбран"}</h2>
            </div>
            {selectedDocument ? <span className={`status-pill tone-${getDocumentTone(selectedDocument)}`}>{formatDocumentStatus(selectedDocument.status)}</span> : null}
          </div>
          {selectedDocument ? (
            <div className="document-graph-canvas">
              <svg className="document-graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                {graph.edges.map((edge) => {
                  const from = nodeById.get(edge.from);
                  const to = nodeById.get(edge.to);
                  if (!from || !to) {
                    return null;
                  }
                  return <line key={edge.id} className={`graph-edge tone-${edge.tone}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
                })}
              </svg>
              {graph.nodes.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  className={`graph-node graph-node-${node.kind} tone-${node.tone} ${node.kind === "requirement" && selectedRequirementId === node.id.replace("requirement-", "") ? "active" : ""}`}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  onClick={() => {
                    if (node.kind === "requirement") {
                      onSelectRequirement(node.id.replace("requirement-", ""));
                    }
                  }}
                >
                  <span>{node.kind}</span>
                  <strong>{node.label}</strong>
                  <small>{node.meta}</small>
                </button>
              ))}
              {graph.nodes.length === 1 ? (
                <div className="graph-empty-note">
                  Связей пока нет. Создайте отчет по этому документу или дождитесь анализа, чтобы появились requirements, risks и XAI/evidence.
                </div>
              ) : null}
            </div>
          ) : (
            <div className="empty-state">Документ не выбран.</div>
          )}
        </section>

        <aside className="panel graph-history-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">История документа</p>
              <h2>Все события</h2>
            </div>
            <span>{history.length}</span>
          </div>
          {history.length === 0 ? (
            <p className="helper-text">Для выбранного документа история пока не найдена.</p>
          ) : (
            <div className="graph-history-list">
              {history.map((item) => (
                <article key={item.id} className={`graph-history-item tone-${item.tone}`}>
                  <time>{formatDateTime(item.createdAt)}</time>
                  <strong>{item.title}</strong>
                  <p>{compactText(item.body, 260)}</p>
                  <span>{compactText(item.meta, 180)}</span>
                </article>
              ))}
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
