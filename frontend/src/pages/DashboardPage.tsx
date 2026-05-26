import type { Dashboard, NotificationItem } from "../lib/types";
import { getReadinessMeta, type DashboardSignal } from "../lib/ui";
import { PageGuide } from "../components/PageGuide";

type Props = {
  dashboard: Dashboard | null;
  notifications: NotificationItem[];
  signals: DashboardSignal[];
};

export function DashboardPage({ dashboard, notifications, signals }: Props) {
  const toneLabel: Record<DashboardSignal["tone"], string> = {
    info: "Инфо",
    success: "Ок",
    warning: "Внимание",
    danger: "Критично",
  };

  if (!dashboard) {
    return <div className="panel">Выберите организацию, чтобы открыть дашборд.</div>;
  }

  const readiness = getReadinessMeta(dashboard.readiness_percent);
  const readinessSteps = [
    { title: "Сбор документов", threshold: 0 },
    { title: "Анализ и извлечение", threshold: 40 },
    { title: "Ручная верификация", threshold: 70 },
    { title: "Согласование", threshold: 90 },
  ];

  return (
    <div className="stack">
      <PageGuide
        title="Дашборд организации"
        summary="Это операционный центр системы. Здесь пользователь видит общую готовность, критичные отклонения и следующий шаг: загрузить документы, создать отчет, запустить анализ или отправить результат на согласование."
        blocks={[
          {
            title: "Что смотреть",
            points: [
              "Готовность организации и количество активных отчетов.",
              "Высокие риски, непрочитанные уведомления и отчеты на согласовании.",
              "Последние сигналы, чтобы понять, где процесс тормозится прямо сейчас.",
            ],
          },
          {
            title: "Что отсюда не делать",
            points: [
              "Сюда не загружают файлы и не редактируют требования.",
              "Это обзорная точка входа, а не рабочая форма редактирования.",
            ],
          },
          {
            title: "Куда идти дальше",
            points: [
              "Если документов нет — в раздел «Документы».",
              "Если документы есть, но отчета нет — в раздел «Отчеты».",
              "Если есть риски и пробелы — в разделы «Требования», «Матрица» и «Риски».",
            ],
          },
        ]}
      />
      <section className="hero">
        <div>
          <p className="eyebrow">Организация</p>
          <h1>{dashboard.organization_name}</h1>
          <p className="helper-text">
            Дашборд показывает текущее состояние подготовленного контура: документы, отчеты, требования, риски и рабочие сигналы.
          </p>
        </div>
      </section>
      <section className="panel readiness-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Интерактивная строка заполнения</p>
            <h2>Готовность контура</h2>
          </div>
          <strong>{dashboard.readiness_percent}%</strong>
        </div>
        <p className="helper-text">{readiness.detail}</p>
        <div className="progress-track large-progress">
          <div className={`progress-fill tone-${readiness.tone}`} style={{ width: `${readiness.progress}%` }} />
        </div>
        <div className="readiness-steps">
          {readinessSteps.map((step, index) => {
            const nextThreshold = readinessSteps[index + 1]?.threshold ?? 101;
            const isCompleted = dashboard.readiness_percent >= nextThreshold;
            const isActive = dashboard.readiness_percent >= step.threshold && dashboard.readiness_percent < nextThreshold;
            return (
              <article
                key={step.title}
                className={`readiness-step ${isCompleted ? "complete" : ""} ${isActive ? "active" : ""}`}
              >
                <span>{step.title}</span>
                <strong>{isCompleted ? "Пройдено" : isActive ? "Текущий этап" : "Впереди"}</strong>
              </article>
            );
          })}
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
          <span>{signals.length}</span>
        </div>
        <div className="list">
          {signals.map((signal) => (
            <article key={signal.id} className="list-item signal-item">
              <div>
                <strong>{signal.title}</strong>
                <p>{signal.body}</p>
                {signal.meta ? <p className="eyebrow">{signal.meta}</p> : null}
              </div>
              <span className={`status-pill tone-${signal.tone}`}>{toneLabel[signal.tone]}</span>
            </article>
          ))}
          {signals.length === 0 ? <div className="list-item">Пока нет новых событий.</div> : null}
        </div>
      </section>
      {notifications.length > 0 ? (
        <section className="panel">
          <div className="section-header">
            <h2>Последние уведомления</h2>
            <span>{notifications.length}</span>
          </div>
          <div className="list">
            {notifications.slice(0, 3).map((notification) => (
              <article key={notification.id} className="list-item">
                <div>
                  <strong>{notification.title}</strong>
                  <p>{notification.body}</p>
                </div>
                <span className={`status-pill ${notification.status}`}>{notification.status}</span>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
