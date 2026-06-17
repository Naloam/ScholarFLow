// App shell: a persistent left nav (always visible, current item highlighted)
// + a main content area (Outlet). Solves the legacy "can't find features" problem
// — navigation is never hidden behind collapsible panels.
import { type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const PROJECT_RE = /^\/projects\/([^/]+)/;

function useProjectIdFromPath(): string | null {
  const { pathname } = useLocation();
  const match = PROJECT_RE.exec(pathname);
  return match ? match[1] : null;
}

interface NavItem {
  label: string;
  to: string;
  end?: boolean;
}

function NavList({ items }: { items: NavItem[] }) {
  return (
    <nav className="nav" aria-label="Primary">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `nav__item${isActive ? " nav__item--active" : ""}`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function AppLayout({ children }: { children?: ReactNode }) {
  const projectId = useProjectIdFromPath();

  const items: NavItem[] = [
    { label: "Projects", to: "/", end: true },
  ];
  if (projectId) {
    items.push(
      { label: "Run", to: `/projects/${projectId}` },
      { label: "Workspace", to: `/projects/${projectId}/files` },
      { label: "Report", to: `/projects/${projectId}/report` },
    );
  }
  items.push({ label: "Settings", to: "/settings" });

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">◇</span>
          <span className="brand__name">ScholarFlow</span>
        </div>
        <NavList items={items} />
        <div className="sidebar__foot">research harness · V1</div>
      </aside>
      <main className="content">{children ?? <Outlet />}</main>
    </div>
  );
}
