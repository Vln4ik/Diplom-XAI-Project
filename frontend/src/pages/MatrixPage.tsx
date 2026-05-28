import { PageGuide } from "../components/PageGuide";
import type { ReportMatrixRow } from "../lib/types";
import { formatRequirementStatus, formatRiskLevel, getRiskTone, getScoreTone } from "../lib/ui";

export function MatrixPage({ rows }: { rows: ReportMatrixRow[] }) {
  return (
    <div className="stack">
      <PageGuide
        title="Матрица требований и доказательств"
        summary="Это главный проверочный экран. Здесь видно, какое требование было извлечено, из какого источника оно взято, какими evidence подтверждается и с каким статусом попадает в отчет."
        blocks={[
          {
            title: "Что смотреть",
            points: [
              "Само требование и его нормализованный текст.",
              "Исходный документ и найденные доказательства.",
              "Статус, confidence и уровень риска по каждой строке.",
            ],
          },
          {
            title: "Что отсюда получать",
            points: [
              "Понимание, почему требование подтверждено или не подтверждено.",
              "Список отсутствующих данных и слабых мест доказательной базы.",
              "Основание для ручной проверки перед согласованием отчета.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Начинать ручную верификацию именно с строк со статусами partial, missing и высоким риском.",
              "Сравнивать source и evidence: если они слабые, возвращаться в раздел «Документы».",
              "Использовать матрицу как основной рабочий экран контроля качества анализа.",
            ],
          },
        ]}
      />
      <section className="panel">
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
              <article
                key={row.requirement_id}
                className={`matrix-row tone-${getScoreTone(Math.round(row.confidence_score * 100))}`}
              >
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
                  <strong>{formatRequirementStatus(row.status)}</strong>
                  <div className="status-meter compact-meter">
                    <div className="meter-meta">
                      <span>Сила подтверждения (confidence)</span>
                      <strong>{Math.round(row.confidence_score * 100)}%</strong>
                    </div>
                    <div className="progress-track">
                      <div
                        className={`progress-fill tone-${getScoreTone(Math.round(row.confidence_score * 100))}`}
                        style={{ width: `${Math.round(row.confidence_score * 100)}%` }}
                      />
                    </div>
                  </div>
                  <p className="helper-text">
                    Чем выше этот процент, тем увереннее система в том, что требование подтверждено найденными evidence.
                  </p>
                  <span className={`status-pill tone-${getRiskTone(row.risk_level)}`}>
                    Риск: {formatRiskLevel(row.risk_level)}
                  </span>
                  <p>{row.included_in_report ? "В отчёте" : "Не включено"}</p>
                  {row.system_comment ? <p>Система: {row.system_comment}</p> : null}
                  {row.user_comment ? <p>Пользователь: {row.user_comment}</p> : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
