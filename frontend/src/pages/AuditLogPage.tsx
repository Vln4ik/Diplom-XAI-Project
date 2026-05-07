import type { AuditLogItem } from "../lib/types";

type Props = {
  logs: AuditLogItem[];
};

export function AuditLogPage({ logs }: Props) {
  return (
    <div className="panel">
      <div className="section-header">
        <h2>Журнал действий</h2>
        <span>{logs.length}</span>
      </div>
      <div className="list">
        {logs.map((log) => (
          <article key={log.id} className="list-item">
            <div className="audit-entry">
              <div className="section-header">
                <strong>{log.action}</strong>
                <span className="eyebrow">{new Date(log.created_at).toLocaleString("ru-RU")}</span>
              </div>
              <p>
                {log.entity_type}
                {log.entity_id ? ` · ${log.entity_id}` : ""}
              </p>
              <p>
                {log.user_full_name ?? "Системное действие"}
                {log.user_email ? ` · ${log.user_email}` : ""}
              </p>
              <pre className="audit-details">{JSON.stringify(log.details, null, 2)}</pre>
            </div>
          </article>
        ))}
        {logs.length === 0 ? <div className="list-item">Записей аудита пока нет.</div> : null}
      </div>
    </div>
  );
}
