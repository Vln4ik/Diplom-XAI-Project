import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { logout } from "../lib/api";
import type { UiTask } from "../lib/ui";
import { ActivityPanel } from "./ActivityPanel";
import { usePageGuide } from "./PageGuideContext";

type LayoutProps = {
  organizationName?: string | null;
  activeTasks: UiTask[];
  floatingWidget?: ReactNode;
};

export function Layout({ organizationName, activeTasks, floatingWidget }: LayoutProps) {
  const { guide } = usePageGuide();
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  useEffect(() => {
    setIsHelpOpen(false);
  }, [guide?.title]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand brand-block brand-block-compact" to="/" aria-label="На главную страницу EvidenceXAI">
          <span className="brand-mark">EX.ai</span>
        </Link>
        <nav className="nav">
          <NavLink to="/">Дашборд</NavLink>
          <NavLink to="/organizations">Организации</NavLink>
        </nav>
        <div className="sidebar-footnote">
          <span className="eyebrow">Рабочее пространство EX.AI</span>
          <p>EvidenceXAI объединяет документы, доказательства, XAI и итоговый отчёт в один управляемый контур.</p>
        </div>
        <button
          className="ghost-button"
          onClick={() => {
            logout();
            window.location.href = "/login";
          }}
        >
          Выйти из аккаунта
        </button>
      </aside>
      <main className="content">
        <header className="workspace-topbar">
          <div className="workspace-brand-copy">
            <span className="eyebrow">EvidenceXAI</span>
            <strong>Рабочий контур проверки</strong>
            <Link className="topbar-org-link topbar-org-under" to="/organizations">
              {organizationName ? `Организация: ${organizationName}` : "Выбрать организацию"}
            </Link>
          </div>
          <nav className="topbar-nav" aria-label="Навигация по активной организации">
            <NavLink to="/documents">Документы</NavLink>
            <NavLink to="/reports">Отчеты</NavLink>
            <NavLink to="/matrix">Матрица</NavLink>
            <NavLink to="/requirements">Требования</NavLink>
            <NavLink to="/risks">Риски</NavLink>
            <NavLink to="/explanations">XAI</NavLink>
          </nav>
          <div className="workspace-topbar-actions">
            <div className="topbar-help">
              <span className="topbar-brand-mini">EX.AI</span>
              <button
                type="button"
                className="help-button"
                disabled={!guide}
                onClick={() => setIsHelpOpen((current) => !current)}
                aria-label="Открыть подсказку по текущему разделу"
                aria-expanded={isHelpOpen}
              >
                ?
              </button>
              {guide && isHelpOpen ? (
                <aside className="help-popover">
                  <div className="help-popover-header">
                    <div>
                      <span className="eyebrow">{guide.eyebrow ?? "Подсказка по разделу"}</span>
                      <h2>{guide.title}</h2>
                    </div>
                    <button type="button" className="modal-close" onClick={() => setIsHelpOpen(false)} aria-label="Закрыть подсказку">
                      ×
                    </button>
                  </div>
                  <p>{guide.summary}</p>
                  <div className="help-popover-grid">
                    {guide.blocks.map((block) => (
                      <article key={block.title} className="help-card">
                        <h3>{block.title}</h3>
                        <ul>
                          {block.points.map((point) => (
                            <li key={point}>{point}</li>
                          ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                </aside>
              ) : null}
            </div>
          </div>
        </header>
        <ActivityPanel tasks={activeTasks} />
        <Outlet />
        {floatingWidget}
      </main>
    </div>
  );
}
