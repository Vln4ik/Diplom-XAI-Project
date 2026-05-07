import type { MemberItem, RiskItem } from "../lib/types";

type Props = {
  risks: RiskItem[];
  members: MemberItem[];
  onUpdateRisk: (
    riskId: string,
    payload: { assigned_to_id?: string | null; status?: string; recommended_action?: string; description?: string },
  ) => Promise<void>;
  onResolveRisk: (riskId: string) => Promise<void>;
};

export function RisksPage({ risks, members, onUpdateRisk, onResolveRisk }: Props) {
  return (
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
            <article key={risk.id} className="list-item">
              <div>
                <strong>{risk.title}</strong>
                <p>
                  {risk.status} · {risk.description}
                </p>
                {risk.recommended_action ? <p>{risk.recommended_action}</p> : null}
              </div>
              <div className="report-actions">
                <span>{risk.risk_level}</span>
                <select
                  value={risk.assigned_to_id ?? ""}
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
                <button type="button" disabled={risk.status === "resolved"} onClick={() => void onResolveRisk(risk.id)}>
                  Закрыть риск
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
