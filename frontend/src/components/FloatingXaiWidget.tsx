import { Link } from "react-router-dom";

import type { Explanation, RequirementItem } from "../lib/types";
import { formatRequirementStatus, formatRiskLevel, getRiskTone, getScoreTone } from "../lib/ui";

type Props = {
  explanation: Explanation | null;
  requirement: RequirementItem | null;
  isOpen: boolean;
  onToggle: () => void;
  routeLabel: string;
};

export function FloatingXaiWidget({ explanation, requirement, isOpen, onToggle, routeLabel }: Props) {
  const confidencePercent = explanation ? Math.round(explanation.confidence_score * 100) : 0;
  const scoreTone = getScoreTone(confidencePercent);
  const riskTone = explanation ? getRiskTone(explanation.risk_level) : "info";
  const evidencePreview = explanation?.evidence_json.slice(0, 2) ?? [];

  return (
    <div className={`floating-xai ${isOpen ? "open" : ""}`}>
      {isOpen ? (
        <aside className="floating-xai-panel">
          <div className="floating-xai-header">
            <div>
              <span className="floating-xai-kicker">XAI</span>
              <h3>Объяснение рядом с действием</h3>
              <p>{routeLabel}</p>
            </div>
            <button type="button" className="floating-xai-close" onClick={onToggle} aria-label="Свернуть XAI">
              ×
            </button>
          </div>

          {requirement ? (
            <div className="floating-xai-body">
              <div className="floating-xai-requirement">
                <strong>{requirement.title}</strong>
                <p>
                  {requirement.category} · {formatRequirementStatus(requirement.status)}
                </p>
              </div>

              {explanation ? (
                <>
                  <div className="floating-xai-summary">
                    <div className="floating-xai-meter">
                      <div className="meter-meta">
                        <span>Уверенность</span>
                        <strong>{confidencePercent}%</strong>
                      </div>
                      <div className="progress-track">
                        <div className={`progress-fill tone-${scoreTone}`} style={{ width: `${confidencePercent}%` }} />
                      </div>
                    </div>
                    <span className={`status-pill tone-${riskTone}`}>Риск: {formatRiskLevel(explanation.risk_level)}</span>
                  </div>

                  <article className="floating-xai-card">
                    <strong>{explanation.conclusion}</strong>
                    <p>{explanation.explanation_text}</p>
                  </article>

                  {explanation.logic_json.length > 0 ? (
                    <article className="floating-xai-card subtle">
                      <h4>Логика решения</h4>
                      <ul>
                        {explanation.logic_json.slice(0, 4).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  ) : null}

                  {evidencePreview.length > 0 ? (
                    <article className="floating-xai-card subtle">
                      <h4>Ключевые evidence</h4>
                      <div className="list compact-list">
                        {evidencePreview.map((item, index) => (
                          <article key={`${item.fragment_id ?? "evidence"}-${index}`} className="list-item compact-item">
                            <strong>{item.document_id ?? "Документ"}</strong>
                            <p>{item.description}</p>
                          </article>
                        ))}
                      </div>
                    </article>
                  ) : null}

                  {explanation.recommended_action ? (
                    <article className="floating-xai-card accent-card">
                      <h4>Рекомендация</h4>
                      <p>{explanation.recommended_action}</p>
                    </article>
                  ) : null}

                  <div className="floating-xai-footer">
                    <Link className="action-button action-light floating-xai-link" to="/explanations">
                      Полный XAI-разбор
                    </Link>
                  </div>
                </>
              ) : (
                <article className="floating-xai-card subtle">
                  <p>
                    Для выбранного требования XAI-объяснение пока не загружено. Запусти анализ или пересчитай артефакты,
                    чтобы панель EX.AI заполнилась актуальной логикой решения.
                  </p>
                </article>
              )}
            </div>
          ) : (
            <div className="floating-xai-body">
              <article className="floating-xai-card subtle">
                <p>
                  Выбери требование, строку матрицы или риск, связанный с требованием. После этого здесь появится
                  компактное XAI-объяснение без перехода в отдельный центр XAI.
                </p>
              </article>
            </div>
          )}
        </aside>
      ) : null}

      <button type="button" className="floating-xai-button" onClick={onToggle} aria-label="Открыть XAI-виджет">
        <span>XAI</span>
      </button>
    </div>
  );
}
