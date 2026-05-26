import type { UiTask } from "../lib/ui";

export function ActivityPanel({ tasks }: { tasks: UiTask[] }) {
  if (tasks.length === 0) {
    return null;
  }

  return (
    <section className="activity-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Текущие операции</p>
          <h2>Система выполняет фоновые действия</h2>
        </div>
        <span>{tasks.length}</span>
      </div>
      <div className="activity-grid">
        {tasks.map((task) => (
          <article key={task.id} className={`activity-card ${task.tone ?? "info"}`}>
            <div className="section-header">
              <strong>{task.title}</strong>
              <span>{task.progress}%</span>
            </div>
            <p>{task.detail}</p>
            <div className="progress-track" aria-hidden="true">
              <div className="progress-fill" style={{ width: `${task.progress}%` }} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
