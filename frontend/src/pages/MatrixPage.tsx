import type { ReportMatrixRow } from "../lib/types";

export function MatrixPage({ rows }: { rows: ReportMatrixRow[] }) {
  return (
    <div className="panel">
      <div className="section-header">
        <h2>Матрица требований и доказательств</h2>
        <span>{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p>Сначала выбери отчёт и запусти анализ.</p>
      ) : (
        <div className="matrix-table">
          <div className="matrix-head">
            <span>Требование</span>
            <span>Источник</span>
            <span>Доказательства</span>
            <span>Статус</span>
          </div>
          {rows.map((row) => (
            <article key={row.requirement_id} className="matrix-row">
              <div>
                <strong>{row.title}</strong>
                <p>{row.category}</p>
                <p>{row.text}</p>
                {row.required_data.length > 0 ? <p>Требуется: {row.required_data.join(", ")}</p> : null}
                {row.found_data.length > 0 ? <p>Найдено: {row.found_data.slice(0, 3).join(" | ")}</p> : null}
              </div>
              <div>
                <strong>{row.source_document_name ?? "—"}</strong>
                <p>{row.source_fragment_text ?? "Источник не зафиксирован"}</p>
              </div>
              <div>
                {row.evidence.length > 0 ? (
                  row.evidence.map((item, index) => (
                    <div key={`${row.requirement_id}-${index}`} className="evidence-snippet">
                      <p>
                        {item.document_name ?? "Документ"} · {Math.round(item.confidence_score * 100)}%
                      </p>
                      <p>{item.fragment_text}</p>
                    </div>
                  ))
                ) : (
                  <p>Доказательства не найдены</p>
                )}
              </div>
              <div>
                <strong>{row.status}</strong>
                <p>{Math.round(row.confidence_score * 100)}% · {row.risk_level}</p>
                <p>{row.included_in_report ? "В отчёте" : "Не включено"}</p>
                {row.system_comment ? <p>Система: {row.system_comment}</p> : null}
                {row.user_comment ? <p>Пользователь: {row.user_comment}</p> : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
