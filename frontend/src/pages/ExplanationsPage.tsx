import type { Explanation } from "../lib/types";

export function ExplanationsPage({ explanation }: { explanation: Explanation | null }) {
  return (
    <div className="panel">
      <div className="section-header">
        <h2>XAI-объяснение</h2>
      </div>
      {explanation ? (
        <div className="stack">
          <article className="explanation-card">
            <strong>{explanation.conclusion}</strong>
            <p>{explanation.explanation_text}</p>
            <p>
              Уверенность: {Math.round(explanation.confidence_score * 100)}% · Риск: {explanation.risk_level}
            </p>
            {explanation.source_document_id ? <p>Источник документа: {explanation.source_document_id}</p> : null}
            {explanation.source_fragment_id ? <p>Источник фрагмента: {explanation.source_fragment_id}</p> : null}
          </article>
          <article className="panel subtle">
            <h3>Логическая цепочка</h3>
            <ul>
              {explanation.logic_json.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            {explanation.recommended_action ? <p>Рекомендация: {explanation.recommended_action}</p> : null}
          </article>
          <article className="panel subtle">
            <h3>Подобранные evidence</h3>
            {explanation.evidence_json.length > 0 ? (
              <div className="list">
                {explanation.evidence_json.map((item, index) => (
                  <article key={`${item.fragment_id ?? "evidence"}-${index}`} className="list-item">
                    <strong>{item.document_id ?? "Документ не указан"}</strong>
                    <p>{item.description}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p>Evidence не сформированы.</p>
            )}
          </article>
        </div>
      ) : (
        <p>Выберите организацию и создайте требования, чтобы получить XAI-объяснение.</p>
      )}
    </div>
  );
}
