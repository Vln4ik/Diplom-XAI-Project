import { PageGuide } from "../components/PageGuide";
import type { MemberItem, RiskItem } from "../lib/types";
import { formatRiskLevel, getRiskTone } from "../lib/ui";

type Props = {
  risks: RiskItem[];
  members: MemberItem[];
  selectedRequirementId: string | null;
  onSelectRequirement: (requirementId: string) => void;
  onUpdateRisk: (
    riskId: string,
    payload: { assigned_to_id?: string | null; status?: string; recommended_action?: string; description?: string },
  ) => Promise<void>;
  onResolveRisk: (riskId: string) => Promise<void>;
};

export function RisksPage({ risks, members, selectedRequirementId, onSelectRequirement, onUpdateRisk, onResolveRisk }: Props) {
  return (
    <div className="stack">
      <PageGuide
        title="Риски"
        summary="В этом разделе пользователь получает не просто список проблем, а рабочий backlog на исправление: что не подтверждено, почему это риск и кто должен его закрыть до финального выпуска отчета."
        blocks={[
          {
            title: "Что отсюда получать",
            points: [
              "Список открытых рисков с уровнем критичности.",
              "Описание проблемы и рекомендуемое действие.",
              "Возможность назначить исполнителя и перевести риск в resolved.",
            ],
          },
          {
            title: "Когда раздел может быть пустым",
            points: [
              "Если все требования подтверждены и пробелов нет.",
              "Если анализ еще не запускался.",
              "Если выбран отчет с уже закрытым контуром рисков.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Работать по приоритету: сначала high и critical.",
              "После закрытия риска возвращаться в требования и запускать повторный анализ.",
              "Назначать ответственных, чтобы раздел был не просто витриной, а рабочим списком действий.",
            ],
          },
        ]}
      />
      <div className="panel">
        <div className="section-header">
          <h2>Риски</h2>
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
