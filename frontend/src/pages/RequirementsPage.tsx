import { useEffect, useMemo, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import type { RequirementItem } from "../lib/types";
import { formatRequirementStatus, formatRiskLevel, getRiskTone, getScoreTone } from "../lib/ui";

type Props = {
  requirements: RequirementItem[];
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

export function RequirementsPage({
  requirements,
  selectedRequirementId,
  onSelectRequirement,
  onConfirm,
  onReject,
  onUpdateRequirement,
  onRefreshArtifacts,
}: Props) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
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

  const filteredRequirements = useMemo(
    () =>
      requirements.filter((requirement) => {
        const haystack = `${requirement.title} ${requirement.category} ${requirement.text}`.toLowerCase();
        const matchesQuery = query.trim() ? haystack.includes(query.trim().toLowerCase()) : true;
        const matchesStatus = statusFilter === "all" ? true : requirement.status === statusFilter;
        return matchesQuery && matchesStatus;
      }),
    [query, requirements, statusFilter],
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
        title="Требования"
        summary="Здесь пользователь работает с извлеченными требованиями: проверяет их применимость, подтверждает или отклоняет результат анализа, вносит ручные правки и при необходимости пересчитывает XAI."
        blocks={[
          {
            title: "Что сюда попадает",
            points: [
              "Нормализованные требования после анализа отчета.",
              "Статусы применимости, confidence, risk level и пользовательские комментарии.",
              "Выявленные системой required_data и found_data.",
            ],
          },
          {
            title: "Что делать пользователю",
            points: [
              "Проверять требования со статусами partial, missing и needs clarification.",
              "Подтверждать, отклонять или вручную корректировать спорные позиции.",
              "После ручной правки пересчитывать XAI, чтобы объяснение соответствовало новой версии требования.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Сначала фильтровать по проблемным статусам, а не просматривать весь реестр подряд.",
              "Использовать массовое подтверждение только для однотипных и уже проверенных строк.",
              "Править здесь смысл требования, а доказательства уточнять через матрицу и документы.",
            ],
          },
        ]}
      />
      <section className="panel">
        <div className="section-header">
          <h2>Реестр требований</h2>
          <span>{filteredRequirements.length}</span>
        </div>
        <div className="form-grid compact">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по требованию" />
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">Все статусы</option>
            <option value="new">{formatRequirementStatus("new")}</option>
            <option value="data_found">{formatRequirementStatus("data_found")}</option>
            <option value="data_partial">{formatRequirementStatus("data_partial")}</option>
            <option value="data_missing">{formatRequirementStatus("data_missing")}</option>
            <option value="confirmed">{formatRequirementStatus("confirmed")}</option>
            <option value="rejected">{formatRequirementStatus("rejected")}</option>
          </select>
        </div>
        <div className="list">
          {filteredRequirements.map((requirement) => (
            <article
              key={requirement.id}
              className={`list-item requirement-card ${selectedRequirementId === requirement.id ? "selected-row" : ""}`}
            >
              <div className="requirement-row">
                <div className="requirement-summary">
                  <strong>{requirement.title}</strong>
                  <p>
                    {requirement.category} · {formatRequirementStatus(requirement.status)} · {requirement.applicability_status}
                  </p>
                  <p>{requirement.text}</p>
                  <div className="requirement-inline-actions">
                    <button
                      type="button"
                      className="action-button action-success"
                      onClick={() => void onConfirm(requirement.id)}
                    >
                      Подтвердить
                    </button>
                    <button
                      type="button"
                      className="action-button action-warning"
                      onClick={() => void onReject(requirement.id)}
                    >
                      Отклонить
                    </button>
                    <button
                      type="button"
                      className="action-button action-light"
                      onClick={() => onSelectRequirement(requirement.id)}
                    >
                      {selectedRequirementId === requirement.id ? "Открыто в редакторе" : "Открыть"}
                    </button>
                  </div>
                </div>
              </div>
              <div className="report-actions">
                <div className="status-meter compact-meter requirement-meter">
                  <div className="meter-meta">
                    <span>Confidence</span>
                    <strong>{Math.round(requirement.confidence_score * 100)}%</strong>
                  </div>
                  <div className="progress-track">
                    <div
                      className={`progress-fill tone-${getScoreTone(Math.round(requirement.confidence_score * 100))}`}
                      style={{ width: `${Math.round(requirement.confidence_score * 100)}%` }}
                    />
                  </div>
                </div>
                <span className={`status-pill tone-${getRiskTone(requirement.risk_level)}`}>
                  Риск: {formatRiskLevel(requirement.risk_level)}
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Ручная правка требования</h2>
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
          <p>Выбери требование из реестра, чтобы отредактировать применимость и комментарий.</p>
        )}
      </section>
    </div>
  );
}
