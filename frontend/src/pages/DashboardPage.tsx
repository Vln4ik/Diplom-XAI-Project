import type { Dashboard, NotificationItem } from "../lib/types";

type Props = {
  dashboard: Dashboard | null;
  notifications: NotificationItem[];
};

export function DashboardPage({ dashboard, notifications }: Props) {
  if (!dashboard) {
    return <div className="panel">Выберите организацию, чтобы открыть дашборд.</div>;
  }

  return (
    <div className="stack">
      <section className="hero">
        <div>
          <p className="eyebrow">Организация</p>
          <h1>{dashboard.organization_name}</h1>
        </div>
        <div className="metric-card accent">
          <span>Готовность</span>
          <strong>{dashboard.readiness_percent}%</strong>
        </div>
      </section>
      <section className="grid">
        <article className="metric-card">
          <span>Активные отчеты</span>
          <strong>{dashboard.active_reports}</strong>
        </article>
        <article className="metric-card">
          <span>На согласовании</span>
          <strong>{dashboard.reports_awaiting_approval}</strong>
        </article>
        <article className="metric-card">
          <span>Обработанные документы</span>
          <strong>{dashboard.processed_documents}</strong>
        </article>
        <article className="metric-card">
          <span>Требования</span>
          <strong>{dashboard.total_requirements}</strong>
        </article>
        <article className="metric-card danger">
          <span>Высокие риски</span>
          <strong>{dashboard.high_risks}</strong>
        </article>
        <article className="metric-card">
          <span>Непрочитанные уведомления</span>
          <strong>{dashboard.unread_notifications}</strong>
        </article>
      </section>
      <section className="panel">
        <div className="section-header">
          <h2>Последние сигналы</h2>
          <span>{notifications.length}</span>
        </div>
        <div className="list">
          {notifications.slice(0, 5).map((notification) => (
            <article key={notification.id} className="list-item">
              <div>
                <strong>{notification.title}</strong>
                <p>{notification.body}</p>
              </div>
              <span className={`status-pill ${notification.status}`}>{notification.status}</span>
            </article>
          ))}
          {notifications.length === 0 ? <div className="list-item">Пока нет новых событий.</div> : null}
        </div>
      </section>
    </div>
  );
}
