import { PageGuide } from "../components/PageGuide";
import type { ExpertiseDecisionItem, MemberItem, RiskItem } from "../lib/types";
import { formatRiskLevel, getRiskTone } from "../lib/ui";

type Props = {
  risks: RiskItem[];
  expertiseDecisions: ExpertiseDecisionItem[];
  members: MemberItem[];
  selectedRequirementId: string | null;
  onSelectRequirement: (requirementId: string) => void;
  onUpdateRisk: (
    riskId: string,
    payload: { assigned_to_id?: string | null; status?: string; recommended_action?: string; description?: string },
  ) => Promise<void>;
  onResolveRisk: (riskId: string) => Promise<void>;
};

function getDecisionTone(decision: ExpertiseDecisionItem): "success" | "warning" | "danger" | "info" {
  if (decision.decision_status === "approved") {
    return "success";
  }
  if (decision.decision_status === "skipped") {
    return "warning";
  }
  return "info";
}

function getDecisionTitle(decision: ExpertiseDecisionItem): string {
  if (decision.decision_status === "approved") {
    return "Одобрено пользователем";
  }
  if (decision.decision_status === "skipped") {
    return "Пропущено пользователем";
  }
  return "Решение пользователя";
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function RisksPage({
  risks,
  expertiseDecisions,
  members,
  selectedRequirementId,
  onSelectRequirement,
  onUpdateRisk,
  onResolveRisk,
}: Props) {
  const approvedCount = expertiseDecisions.filter((decision) => decision.decision_status === "approved").length;
  const skippedCount = expertiseDecisions.filter((decision) => decision.decision_status === "skipped").length;

  return (
    <div className="stack">
      <PageGuide
        title="Риски и решения пользователя"
        summary="Здесь собраны две группы данных: открытые риски по требованиям и все решения, которые пользователь принял в спецпроверке: одобрил вывод или пропустил проблемный файл/пункт."
        blocks={[
          {
            title: "Что отсюда получать",
            points: [
              "Список открытых рисков с уровнем критичности.",
              "Журнал решений пользователя по проверке ПП 145/ПП 87.",
              "Понимание, какие выводы были пропущены и какие были приняты вручную.",
              "Описание проблемы и рекомендуемое действие.",
            ],
          },
          {
            title: "Когда раздел может быть пустым",
            points: [
              "Если все требования подтверждены и пробелов нет.",
              "Если анализ еще не запускался.",
              "Если пользователь еще не нажимал «Одобрить» или «Пропустить» в спецпроверке.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Работать по приоритету: сначала high и critical.",
              "Отдельно пересматривать пропущенные решения: они могут скрывать реальные пробелы пакета.",
              "После закрытия риска возвращаться в требования и запускать повторный анализ.",
              "Назначать ответственных, чтобы раздел был не просто витриной, а рабочим списком действий.",
            ],
          },
        ]}
      />
      <section className="panel decision-log-panel">
        <div className="section-header">
          <h2>Решения пользователя по спецпроверкам</h2>
          <span>{expertiseDecisions.length}</span>
        </div>
        <div className="decision-log-summary">
          <article className="decision-summary-card tone-success">
            <span>Одобрено</span>
            <strong>{approvedCount}</strong>
            <p>Пользователь согласился с выводом модели и оставил его в маршруте проверки.</p>
          </article>
          <article className="decision-summary-card tone-warning">
            <span>Пропущено</span>
            <strong>{skippedCount}</strong>
            <p>Пользователь исключил вывод, файл или пункт из дальнейшего анализа.</p>
          </article>
        </div>
        {expertiseDecisions.length === 0 ? (
          <p className="helper-text">
            Решений пока нет. Они появятся после действий «Одобрить» или «Пропустить» в блоке замечаний спецотчета.
          </p>
        ) : (
          <div className="decision-log-list">
            {expertiseDecisions.map((decision) => {
              const tone = getDecisionTone(decision);
              return (
                <article key={decision.id} className={`decision-log-card tone-${tone}`}>
                  <div className="decision-log-main">
                    <div className="decision-log-head">
                      <span className={`decision-badge tone-${tone}`}>{getDecisionTitle(decision)}</span>
                      <span>{formatDateTime(decision.created_at)}</span>
                    </div>
                    <strong>{decision.finding_title}</strong>
                    <p>{decision.finding_description}</p>
                    <div className="decision-log-meta">
                      <span>{decision.report_title}</span>
                      <span>{decision.stage_title}</span>
                      <span>{decision.document_name}</span>
                    </div>
                  </div>
                  <div className="decision-log-xai">
                    <strong>Почему это решение важно</strong>
                    <p>{decision.decision_label}</p>
                    <p>Нормативная база: {decision.normative_basis}</p>
                    <p>Источник: {decision.source_ref}</p>
                    <p>Рекомендация: {decision.recommendation}</p>
                    {decision.xai_summary.length > 0 ? (
                      <ul>
                        {decision.xai_summary.slice(0, 3).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
      <div className="panel">
        <div className="section-header">
          <h2>Открытые риски по требованиям</h2>
          <span>{risks.length}</span>
        </div>
        {risks.length === 0 ? (
          <p className="helper-text">
            Для текущей организации рисков не найдено. Это нормально, если все требования подтверждены. Чтобы увидеть
            риски в demo-сценарии, создай отдельный отчет без доказательных документов или без части исходных данных.
          </p>
        ) : (
          <div className="list">
            {risks.map((risk) => (
              <article
                key={risk.id}
                className={`list-item risk-card tone-${getRiskTone(risk.risk_level)} ${
                  risk.requirement_id && selectedRequirementId === risk.requirement_id ? "selected-row" : ""
                }`}
                onClick={() => {
                  if (risk.requirement_id) {
                    onSelectRequirement(risk.requirement_id);
                  }
                }}
                role={risk.requirement_id ? "button" : undefined}
                tabIndex={risk.requirement_id ? 0 : undefined}
                onKeyDown={(event) => {
                  if (!risk.requirement_id) {
                    return;
                  }
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectRequirement(risk.requirement_id);
                  }
                }}
              >
                <div>
                  <strong>{risk.title}</strong>
                  <p>
                    {risk.status} · {risk.description}
                  </p>
                  {risk.recommended_action ? <p>{risk.recommended_action}</p> : null}
                  {risk.requirement_id ? <p className="helper-text">Клик по карточке открывает XAI по связанному требованию.</p> : null}
                </div>
                <div className="report-actions">
                  <span className={`status-pill tone-${getRiskTone(risk.risk_level)}`}>{formatRiskLevel(risk.risk_level)}</span>
                  <select
                    value={risk.assigned_to_id ?? ""}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) =>
                      void onUpdateRisk(risk.id, {
                        assigned_to_id: event.target.value || null,
                      })
                    }
                  >
                    <option value="">Без исполнителя</option>
                    {members.map((member) => (
                      <option key={member.user_id} value={member.user_id}>
                        {member.full_name} · {member.role}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={risk.status === "resolved"}
                    onClick={(event) => {
                      event.stopPropagation();
                      void onResolveRisk(risk.id);
                    }}
                  >
                    Закрыть риск
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
