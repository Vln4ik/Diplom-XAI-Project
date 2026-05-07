import { useEffect, useState } from "react";

import type { ReportSection, ReportVersion } from "../lib/types";

type Props = {
  reportId: string | null;
  sections: ReportSection[];
  versions: ReportVersion[];
  onSaveSection: (reportId: string, sectionId: string, payload: { content: string }) => Promise<void>;
  onRestoreVersion: (versionId: string) => Promise<void>;
};

export function ReportEditorPage({ reportId, sections, versions, onSaveSection, onRestoreVersion }: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    const nextDrafts: Record<string, string> = {};
    for (const section of sections) {
      nextDrafts[section.id] = section.content;
    }
    setDrafts(nextDrafts);
  }, [sections]);

  return (
    <div className="stack">
      <section className="panel">
        <div className="section-header">
          <h2>Версии отчета</h2>
          <span>{versions.length}</span>
        </div>
        {!reportId ? (
          <p className="helper-text">Сначала на вкладке &quot;Отчеты&quot; нажми &quot;Открыть&quot; у нужного отчета.</p>
        ) : versions.length > 0 ? (
          <div className="list">
            {versions.map((version) => (
              <article key={version.id} className="list-item">
                <div>
                  <strong>Версия {version.version_number}</strong>
                  <p>
                    {version.report_status} · {version.sections_json.length} разделов · {version.matrix_json.length} строк матрицы
                  </p>
                </div>
                <div className="report-actions">
                  <span>{new Date(version.created_at).toLocaleString("ru-RU")}</span>
                  <button type="button" disabled={!reportId} onClick={() => void onRestoreVersion(version.id)}>
                    Восстановить
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p>Версии появятся после генерации отчета.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Редактор отчета</h2>
          <span>{sections.length} разделов</span>
        </div>
        {!reportId ? (
          <p className="helper-text">Выбери отчет на вкладке &quot;Отчеты&quot;, чтобы открыть его разделы.</p>
        ) : sections.length === 0 ? (
          <p className="helper-text">
            После анализа редактор еще пуст. Нажми &quot;Генерация&quot; на вкладке &quot;Отчеты&quot;, чтобы создать
            разделы отчета.
          </p>
        ) : (
          <div className="list">
            {sections.map((section) => (
              <article key={section.id} className="editor-card">
                <header>
                  <strong>
                    {section.order_number}. {section.title}
                  </strong>
                  <span>{section.status}</span>
                </header>
                <textarea
                  className="section-editor"
                  value={drafts[section.id] ?? ""}
                  onChange={(event) => setDrafts((current) => ({ ...current, [section.id]: event.target.value }))}
                />
                <div className="report-actions">
                  <button
                    type="button"
                    disabled={!reportId}
                    onClick={async () => {
                      if (!reportId) {
                        return;
                      }
                      await onSaveSection(reportId, section.id, { content: drafts[section.id] ?? "" });
                    }}
                  >
                    Сохранить раздел
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
