import { PageGuide } from "../components/PageGuide";
import type { NotificationItem } from "../lib/types";
import { formatNotificationStatus } from "../lib/ui";

type Props = {
  notifications: NotificationItem[];
  onMarkRead: (notificationId: string) => Promise<void>;
  onMarkAllRead: () => Promise<void>;
};

export function NotificationsPage({ notifications, onMarkRead, onMarkAllRead }: Props) {
  return (
    <div className="stack">
      <PageGuide
        title="Уведомления"
        summary="Раздел нужен для событий, которые требуют внимания пользователя: обновления статусов, переходы отчетов между этапами и сигналы о ручной проверке."
        blocks={[
          {
            title: "Что отсюда получать",
            points: [
              "Список непрочитанных и прочитанных событий.",
              "Быстрый обзор, что изменилось в рабочем контуре.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Использовать как журнал последних событий, а не как главный рабочий экран.",
              "Если событие критично, переходить из уведомления в соответствующий раздел: документы, отчеты, риски.",
            ],
          },
        ]}
      />
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
                  <span className={`status-pill ${notification.status}`}>{formatNotificationStatus(notification.status)}</span>
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
