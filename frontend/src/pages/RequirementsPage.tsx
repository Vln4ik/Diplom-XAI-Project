import { useEffect, useMemo, useState } from "react";

import type { RequirementItem } from "../lib/types";

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
  onBulkUpdate: (payload: {
    requirement_ids: string[];
    status?: string;
    applicability_status?: string;
    user_comment?: string;
  }) => Promise<void>;
  onRefreshArtifacts: (requirementId: string) => Promise<void>;
};

export function RequirementsPage({
  requirements,
  selectedRequirementId,
  onSelectRequirement,
  onConfirm,
  onReject,
  onUpdateRequirement,
  onBulkUpdate,
  onRefreshArtifacts,
}: Props) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
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

  function toggleSelected(requirementId: string) {
    setSelectedIds((current) =>
      current.includes(requirementId) ? current.filter((item) => item !== requirementId) : [...current, requirementId],
    );
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="section-header">
          <h2>Реестр требований</h2>
          <span>{filteredRequirements.length}</span>
        </div>
        <div className="form-grid compact">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по требованию" />
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">Все статусы</option>
            <option value="new">new</option>
            <option value="data_found">data_found</option>
            <option value="data_partial">data_partial</option>
            <option value="data_missing">data_missing</option>
            <option value="confirmed">confirmed</option>
            <option value="rejected">rejected</option>
          </select>
        </div>
        <div className="report-actions bulk-bar">
          <span>Выбрано: {selectedIds.length}</span>
          <button
            type="button"
            disabled={selectedIds.length === 0}
            onClick={() => void onBulkUpdate({ requirement_ids: selectedIds, status: "confirmed" })}
          >
            Подтвердить выбранные
          </button>
          <button
            type="button"
            disabled={selectedIds.length === 0}
            onClick={() => void onBulkUpdate({ requirement_ids: selectedIds, status: "rejected" })}
          >
            Отклонить выбранные
          </button>
        </div>
        <div className="list">
          {filteredRequirements.map((requirement) => (
            <article key={requirement.id} className="list-item">
              <div className="requirement-row">
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(requirement.id)}
                    onChange={() => toggleSelected(requirement.id)}
                  />
                </label>
                <div className="requirement-summary">
                  <strong>{requirement.title}</strong>
                  <p>
                    {requirement.category} · {requirement.status} · {requirement.applicability_status}
                  </p>
                  <p>{requirement.text}</p>
                </div>
              </div>
              <div className="report-actions">
                <span>
                  {Math.round(requirement.confidence_score * 100)}% · {requirement.risk_level}
                </span>
                <button type="button" onClick={() => onSelectRequirement(requirement.id)}>
                  {selectedRequirementId === requirement.id ? "Выбрано" : "Объяснение"}
                </button>
                <button type="button" onClick={() => onConfirm(requirement.id)}>
                  Подтвердить
                </button>
                <button type="button" onClick={() => onReject(requirement.id)}>
                  Отклонить
                </button>
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
              <option value="applicable">applicable</option>
              <option value="not_applicable">not_applicable</option>
              <option value="needs_clarification">needs_clarification</option>
            </select>
            <select value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
              <option value="new">new</option>
              <option value="data_found">data_found</option>
              <option value="data_partial">data_partial</option>
              <option value="data_missing">data_missing</option>
              <option value="confirmed">confirmed</option>
              <option value="rejected">rejected</option>
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
              <button type="button" onClick={() => void onRefreshArtifacts(selectedRequirement.id)}>
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
