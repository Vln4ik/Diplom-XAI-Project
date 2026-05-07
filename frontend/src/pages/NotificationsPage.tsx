import type { NotificationItem } from "../lib/types";

type Props = {
  notifications: NotificationItem[];
  onMarkRead: (notificationId: string) => Promise<void>;
  onMarkAllRead: () => Promise<void>;
};

export function NotificationsPage({ notifications, onMarkRead, onMarkAllRead }: Props) {
  return (
    <div className="stack">
      <section className="panel">
        <div className="section-header">
          <h2>Уведомления</h2>
          <div className="report-actions">
            <span>{notifications.length}</span>
            <button type="button" onClick={() => onMarkAllRead()}>
              Прочитать все
            </button>
          </div>
        </div>
        <div className="list">
          {notifications.map((notification) => (
            <article key={notification.id} className="list-item">
              <div>
                <div className="section-header">
                  <strong>{notification.title}</strong>
                  <span className={`status-pill ${notification.status}`}>{notification.status}</span>
                </div>
                <p>{notification.body}</p>
                <p className="eyebrow">{new Date(notification.created_at).toLocaleString("ru-RU")}</p>
              </div>
              <div className="report-actions">
                <button type="button" disabled={notification.status === "read"} onClick={() => onMarkRead(notification.id)}>
                  Отметить прочитанным
                </button>
              </div>
            </article>
          ))}
          {notifications.length === 0 ? <div className="list-item">Уведомлений пока нет.</div> : null}
        </div>
      </section>
    </div>
  );
}
