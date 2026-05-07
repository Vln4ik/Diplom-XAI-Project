import { Link, NavLink, Outlet } from "react-router-dom";

import { logout } from "../lib/api";

type LayoutProps = {
  organizationId: string | null;
  onSelectOrganization: (value: string) => void;
  organizations: { id: string; name: string }[];
  unreadNotifications: number;
};

export function Layout({ organizationId, onSelectOrganization, organizations, unreadNotifications }: LayoutProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          XAI Report Builder
        </Link>
        <select
          className="org-switcher"
          value={organizationId ?? ""}
          onChange={(event) => onSelectOrganization(event.target.value)}
        >
          <option value="" disabled>
            Выберите организацию
          </option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>
              {organization.name}
            </option>
          ))}
        </select>
        <nav className="nav">
          <NavLink to="/">Дашборд</NavLink>
          <NavLink to="/organizations">Организации</NavLink>
          <NavLink to="/documents">Документы</NavLink>
          <NavLink to="/reports">Отчеты</NavLink>
          <NavLink to="/matrix">Матрица</NavLink>
          <NavLink to="/requirements">Требования</NavLink>
          <NavLink to="/risks">Риски</NavLink>
          <NavLink to="/editor">Редактор отчета</NavLink>
          <NavLink to="/explanations">Объяснения</NavLink>
          <NavLink to="/notifications">
            Уведомления
            {unreadNotifications > 0 ? <span className="nav-badge">{unreadNotifications}</span> : null}
          </NavLink>
          <NavLink to="/audit">Аудит</NavLink>
        </nav>
        <button
          className="ghost-button"
          onClick={() => {
            logout();
            window.location.href = "/login";
          }}
        >
          Выйти
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
