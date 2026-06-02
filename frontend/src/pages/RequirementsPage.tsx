import { useEffect, useMemo, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import { fetchEstimateExpertiseWorkflow } from "../lib/api";
import {
  isActiveDocumentRequirement,
  isActiveEstimateFinding,
  isActiveRequirement,
  isActiveRiskRequirement,
} from "../lib/activeRequirements";
import type { EstimateExpertiseFinding, EstimateExpertiseWorkflow } from "../lib/estimateExpertise";
import { isStateExpertiseEstimateCostReport } from "../lib/reportTypes";
import type { DocumentItem, ReportItem, RequirementItem, RiskItem } from "../lib/types";
import {
  formatDocumentStatus,
  formatRequirementStatus,
  formatReportType,
  formatRiskLevel,
  getDocumentProcessingReason,
  getRiskTone,
  getScoreTone,
  type UiTone,
} from "../lib/ui";

type Props = {
  documents: DocumentItem[];
  reports: ReportItem[];
  requirements: RequirementItem[];
  risks: RiskItem[];
  selectedRequirementId: string | null;
  onSelectRequirement: (requirementId: string) => void;
  onConfirm: (requirementId: string) => Promise<void>;
  onReject: (requirementId: string) => Promise<void>;
  onUpdateRequirement: (
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
  ) => Promise<void>;
  onRefreshArtifacts: (requirementId: string) => Promise<void>;
};

type ActiveAiRequirementKind = "requirement" | "document" | "finding" | "risk";

type ActiveAiRequirement = {
  id: string;
  kind: ActiveAiRequirementKind;
  kindLabel: string;
  title: string;
  description: string;
  source: string;
  statusLabel: string;
  recommendation: string;
  tone: UiTone;
  confidencePercent?: number;
  normativeBasis?: string;
  requirementId?: string;
};

const ACTIVE_AI_KIND_LABELS: Record<ActiveAiRequirementKind | "all", string> = {
  all: "Все типы",
  requirement: "Нормализованные требования",
  document: "Документы",
  finding: "Спецпроверка",
  risk: "Риски",
};

const TONE_SORT_WEIGHT: Record<UiTone, number> = {
  danger: 0,
  warning: 1,
  info: 2,
  success: 3,
};

function getRequirementRecommendation(requirement: RequirementItem): string {
  if (requirement.status === "data_missing") {
    return "Загрузить недостающие данные, заменить источник или отклонить требование, если оно неприменимо.";
  }
  if (requirement.status === "data_partial") {
    return "Проверить найденные evidence, уточнить комментарий и подтвердить либо отклонить вывод ИИ.";
  }
  if (requirement.status === "data_found") {
    return "Проверить корректность вывода ИИ и подтвердить требование вручную.";
  }
  if (requirement.applicability_status === "needs_clarification") {
    return "Определить применимость требования и сохранить ручной комментарий.";
  }
  return "Проверить требование и закрыть его решением пользователя.";
}

function getRequirementTone(requirement: RequirementItem): UiTone {
  if (requirement.status === "data_missing" || ["high", "critical"].includes(requirement.risk_level)) {
    return "danger";
  }
  if (requirement.status === "data_partial" || requirement.applicability_status === "needs_clarification") {
    return "warning";
  }
  return "info";
}

function getDocumentAction(document: DocumentItem): { title: string; recommendation: string; tone: UiTone } {
  if (document.status === "failed") {
    return {
      title: `Обновить файл: ${document.file_name}`,
      recommendation: "Загрузить корректную копию файла или повторить обработку после исправления причины ошибки.",
      tone: "danger",
    };
  }
  if (document.status === "requires_review") {
    return {
      title: `Проверить корректность извлечения: ${document.file_name}`,
      recommendation: "Открыть файл, проверить качество текста/OCR и при необходимости заменить источник.",
      tone: "warning",
    };
  }
  if (document.status === "outdated") {
    return {
      title: `Обновить актуальность файла: ${document.file_name}`,
      recommendation: "Загрузить актуальную версию документа или исключить старую копию из проверки.",
      tone: "warning",
    };
  }
  return {
    title: `Дождаться обработки: ${document.file_name}`,
    recommendation: "Дождаться завершения pipeline, после чего ИИ сможет использовать документ в evidence linking.",
    tone: "info",
  };
}

function getRiskStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "Новый",
    in_progress: "В работе",
    needs_review: "Нужна проверка",
    resolved: "Закрыт",
  };
  return labels[status] ?? status;
}

function getFindingTone(finding: EstimateExpertiseFinding): UiTone {
  if (finding.severity === "danger") {
    return "danger";
  }
  if (finding.severity === "warning") {
    return "warning";
  }
  return "info";
}

function buildActiveAiRequirements(params: {
  documents: DocumentItem[];
  reports: ReportItem[];
  requirements: RequirementItem[];
  risks: RiskItem[];
  estimateWorkflows: Record<string, EstimateExpertiseWorkflow>;
}): ActiveAiRequirement[] {
  const requirementActions = params.requirements.filter(isActiveRequirement).map((requirement): ActiveAiRequirement => ({
    id: `requirement-${requirement.id}`,
    kind: "requirement",
    kindLabel: "Требование ИИ",
    title:
      requirement.status === "data_found"
        ? `Проверить корректность: ${requirement.title}`
        : `Закрыть требование: ${requirement.title}`,
    description: requirement.text,
    source: `${requirement.category} · ${requirement.applicability_status}`,
    statusLabel: formatRequirementStatus(requirement.status),
    recommendation: getRequirementRecommendation(requirement),
    tone: getRequirementTone(requirement),
    confidencePercent: Math.round(requirement.confidence_score * 100),
    normativeBasis: requirement.applicability_reason ?? undefined,
    requirementId: requirement.id,
  }));

  const documentActions = params.documents.filter(isActiveDocumentRequirement).map((document): ActiveAiRequirement => {
    const action = getDocumentAction(document);
    const reason = getDocumentProcessingReason(document);
    return {
      id: `document-${document.id}`,
      kind: "document",
      kindLabel: "Документ",
      title: action.title,
      description: reason ?? "Документ сейчас требует внимания пользователя или завершения pipeline.",
      source: document.relative_path || document.original_file_name || document.file_name,
      statusLabel: formatDocumentStatus(document.status),
      recommendation: action.recommendation,
      tone: action.tone,
    };
  });

  const riskActions = params.risks.filter(isActiveRiskRequirement).map((risk): ActiveAiRequirement => ({
    id: `risk-${risk.id}`,
    kind: "risk",
    kindLabel: "Риск",
    title: `Разобрать риск: ${risk.title}`,
    description: risk.description,
    source: risk.requirement_id ? `Связанное требование: ${risk.requirement_id.slice(0, 8)}` : "Общий риск отчета",
    statusLabel: `${getRiskStatusLabel(risk.status)} · ${formatRiskLevel(risk.risk_level)}`,
    recommendation: risk.recommended_action ?? "Проверить риск, принять решение и закрыть его после устранения.",
    tone: getRiskTone(risk.risk_level),
  }));

  const findingActions = params.reports
    .filter((report) => isStateExpertiseEstimateCostReport(report.report_type))
    .flatMap((report) => {
      const workflow = params.estimateWorkflows[report.id];
      if (!workflow) {
        return [];
      }
      return workflow.stages.flatMap((stage) =>
        stage.findings.filter(isActiveEstimateFinding).map((finding): ActiveAiRequirement => ({
          id: `finding-${finding.id}`,
          kind: "finding",
          kindLabel: "Спецпроверка",
          title: finding.title,
          description: finding.description,
          source: `${report.title} · ${formatReportType(report.report_type)} · ${stage.shortTitle} · ${finding.documentName}`,
          statusLabel: finding.decision?.label ?? "Требуется решение",
          recommendation: finding.recommendation,
          tone: getFindingTone(finding),
          confidencePercent: Math.round(finding.confidence * 100),
          normativeBasis: `${finding.normativeBasis} · ${finding.sourceRef}`,
        })),
      );
    });

  return [...findingActions, ...documentActions, ...requirementActions, ...riskActions].sort((left, right) => {
    return TONE_SORT_WEIGHT[left.tone] - TONE_SORT_WEIGHT[right.tone] || left.kind.localeCompare(right.kind, "ru");
  });
}

export function RequirementsPage({
  documents,
  reports,
  requirements,
  risks,
  selectedRequirementId,
  onSelectRequirement,
  onConfirm,
  onReject,
  onUpdateRequirement,
  onRefreshArtifacts,
}: Props) {
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<ActiveAiRequirementKind | "all">("all");
  const [estimateWorkflows, setEstimateWorkflows] = useState<Record<string, EstimateExpertiseWorkflow>>({});
  const [draftTitle, setDraftTitle] = useState("");
  const [draftCategory, setDraftCategory] = useState("");
  const [draftText, setDraftText] = useState("");
  const [draftApplicability, setDraftApplicability] = useState("needs_clarification");
  const [draftStatus, setDraftStatus] = useState("needs_clarification");
  const [draftComment, setDraftComment] = useState("");
  const [draftApplicabilityReason, setDraftApplicabilityReason] = useState("");

  const selectedRequirement = useMemo(
    () => requirements.find((requirement) => requirement.id === selectedRequirementId) ?? null,
    [requirements, selectedRequirementId],
  );

  useEffect(() => {
    const specialReports = reports.filter((report) => isStateExpertiseEstimateCostReport(report.report_type));
    if (specialReports.length === 0) {
      setEstimateWorkflows({});
      return;
    }

    let cancelled = false;
    Promise.allSettled(
      specialReports.map(async (report) => ({
        reportId: report.id,
        workflow: await fetchEstimateExpertiseWorkflow(report.id),
      })),
    ).then((results) => {
      if (cancelled) {
        return;
      }
      const nextWorkflows = Object.fromEntries(
        results
          .filter((result): result is PromiseFulfilledResult<{ reportId: string; workflow: EstimateExpertiseWorkflow }> => result.status === "fulfilled")
          .map((result) => [result.value.reportId, result.value.workflow]),
      );
      setEstimateWorkflows(nextWorkflows);
    });

    return () => {
      cancelled = true;
    };
  }, [reports]);

  const activeAiRequirements = useMemo(
    () => buildActiveAiRequirements({ documents, reports, requirements, risks, estimateWorkflows }),
    [documents, estimateWorkflows, reports, requirements, risks],
  );

  const filteredActiveAiRequirements = useMemo(
    () =>
      activeAiRequirements.filter((item) => {
        const haystack = `${item.title} ${item.description} ${item.source} ${item.recommendation}`.toLowerCase();
        const matchesQuery = query.trim() ? haystack.includes(query.trim().toLowerCase()) : true;
        const matchesKind = kindFilter === "all" ? true : item.kind === kindFilter;
        return matchesQuery && matchesKind;
      }),
    [activeAiRequirements, kindFilter, query],
  );

  useEffect(() => {
    if (!selectedRequirement) {
      return;
    }
    setDraftTitle(selectedRequirement.title);
    setDraftCategory(selectedRequirement.category);
    setDraftText(selectedRequirement.text);
    setDraftApplicability(selectedRequirement.applicability_status);
    setDraftStatus(selectedRequirement.status);
    setDraftComment(selectedRequirement.user_comment ?? "");
    setDraftApplicabilityReason(selectedRequirement.applicability_reason ?? "");
  }, [selectedRequirement]);

  return (
    <div className="stack">
      <PageGuide
        title="Активные требования ИИ"
        summary="Вкладка показывает только текущие действия, которые система требует от пользователя: проверить корректность вывода, заменить файл, закрыть риск или принять решение по замечанию спецпроверки."
        blocks={[
          {
            title: "Что сюда попадает",
            points: [
              "Незакрытые findings спецпроверки ПП 145/87.",
              "Документы со статусом ошибки, ручной проверки, ожидания или обработки.",
              "Неподтвержденные требования и открытые риски.",
            ],
          },
          {
            title: "Что считается закрытым",
            points: [
              "Требование подтверждено, отклонено, включено в отчет или признано неприменимым.",
              "Finding спецпроверки получил решение пользователя: одобрено, пропущено или заменено.",
              "Документ обработан без активной ошибки, а риск переведен в закрытый статус.",
            ],
          },
          {
            title: "Связь с дашбордом",
            points: [
              "Если отчет полностью сформирован и этот список пуст, дашборд показывает 100% готовности.",
              "Если здесь есть хотя бы один активный пункт, общий контур остается в рабочем состоянии.",
            ],
          },
        ]}
      />

      <section className="panel active-ai-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Текущий action-list</p>
            <h2>Активные требования от ИИ</h2>
          </div>
          <span className={`status-pill tone-${activeAiRequirements.length > 0 ? "warning" : "success"}`}>
            {activeAiRequirements.length > 0 ? `${activeAiRequirements.length} активно` : "Нет активных"}
          </span>
        </div>
        <div className="form-grid compact">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по активному требованию" />
          <select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as ActiveAiRequirementKind | "all")}>
            {Object.entries(ACTIVE_AI_KIND_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {filteredActiveAiRequirements.length === 0 ? (
          <div className="empty-state">
            {activeAiRequirements.length === 0
              ? "Активных требований ИИ сейчас нет. Если отчет сформирован полностью, дашборд покажет готовность 100%."
              : "По текущему фильтру активных требований не найдено."}
          </div>
        ) : (
          <div className="active-ai-list">
            {filteredActiveAiRequirements.map((item) => (
              <article key={item.id} className={`active-ai-card tone-${item.tone}`}>
                <div className="active-ai-main">
                  <div className="active-ai-head">
                    <span className="eyebrow">{item.kindLabel}</span>
                    <span className={`status-pill tone-${item.tone}`}>{item.statusLabel}</span>
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                  <div className="active-ai-meta">
                    <span>{item.source}</span>
                    {typeof item.confidencePercent === "number" ? (
                      <span className={`status-pill tone-${getScoreTone(item.confidencePercent)}`}>Confidence {item.confidencePercent}%</span>
                    ) : null}
                    {item.normativeBasis ? <span>{item.normativeBasis}</span> : null}
                  </div>
                </div>
                <div className="active-ai-action">
                  <span>Что нужно сделать</span>
                  <p>{item.recommendation}</p>
                  {item.requirementId ? (
                    <div className="requirement-inline-actions">
                      <button type="button" className="action-button action-success" onClick={() => void onConfirm(item.requirementId!)}>
                        Подтвердить
                      </button>
                      <button type="button" className="action-button action-warning" onClick={() => void onReject(item.requirementId!)}>
                        Отклонить
                      </button>
                      <button type="button" className="action-button action-light" onClick={() => onSelectRequirement(item.requirementId!)}>
                        Открыть правку
                      </button>
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Ручная правка нормализованного требования</h2>
          <span>{selectedRequirement ? selectedRequirement.id.slice(0, 8) : "—"}</span>
        </div>
        {selectedRequirement ? (
          <div className="form-grid">
            <input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} placeholder="Заголовок" />
            <input value={draftCategory} onChange={(event) => setDraftCategory(event.target.value)} placeholder="Категория" />
            <textarea
              className="section-editor compact-editor"
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              placeholder="Нормализованный текст требования"
            />
            <select value={draftApplicability} onChange={(event) => setDraftApplicability(event.target.value)}>
              <option value="applicable">Применимо</option>
              <option value="not_applicable">Не применимо</option>
              <option value="needs_clarification">Нужна проверка</option>
            </select>
            <select value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
              <option value="new">{formatRequirementStatus("new")}</option>
              <option value="data_found">{formatRequirementStatus("data_found")}</option>
              <option value="data_partial">{formatRequirementStatus("data_partial")}</option>
              <option value="data_missing">{formatRequirementStatus("data_missing")}</option>
              <option value="confirmed">{formatRequirementStatus("confirmed")}</option>
              <option value="rejected">{formatRequirementStatus("rejected")}</option>
            </select>
            <input
              value={draftApplicabilityReason}
              onChange={(event) => setDraftApplicabilityReason(event.target.value)}
              placeholder="Обоснование применимости"
            />
            <textarea
              className="section-editor compact-editor"
              value={draftComment}
              onChange={(event) => setDraftComment(event.target.value)}
              placeholder="Комментарий пользователя"
            />
            <div className="report-actions">
              <button
                type="button"
                className="action-button action-primary"
                onClick={() =>
                  void onUpdateRequirement(selectedRequirement.id, {
                    title: draftTitle,
                    category: draftCategory,
                    text: draftText,
                    applicability_status: draftApplicability,
                    applicability_reason: draftApplicabilityReason,
                    user_comment: draftComment,
                    status: draftStatus,
                  })
                }
              >
                Сохранить правку
              </button>
              <button
                type="button"
                className="action-button action-secondary"
                onClick={() => void onRefreshArtifacts(selectedRequirement.id)}
              >
                Пересчитать XAI
              </button>
            </div>
            <div className="detail-grid">
              <article className="subtle panel">
                <h3>Требуемые данные</h3>
                {selectedRequirement.required_data.length > 0 ? (
                  <ul>
                    {selectedRequirement.required_data.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Список не сформирован.</p>
                )}
              </article>
              <article className="subtle panel">
                <h3>Найденные данные</h3>
                {selectedRequirement.found_data.length > 0 ? (
                  <ul>
                    {selectedRequirement.found_data.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Подтверждения пока не найдены.</p>
                )}
              </article>
            </div>
          </div>
        ) : (
          <p>Выберите активное нормализованное требование из списка выше, чтобы открыть ручную правку.</p>
        )}
      </section>
    </div>
  );
}
