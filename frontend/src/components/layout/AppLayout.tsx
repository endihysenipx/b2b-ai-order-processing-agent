import { NavLink, Outlet } from "react-router-dom";
import { ClipboardList, Database, FileDown, Gauge, MessageSquareWarning, Settings, Users } from "lucide-react";

const navItems = [
  { to: "/", label: "Overview", icon: Gauge },
  { to: "/orders", label: "Orders", icon: ClipboardList },
  { to: "/clients", label: "Clients", icon: Database },
  { to: "/data-export", label: "Data Export", icon: FileDown },
  { to: "/feedback", label: "Feedback & Issues", icon: MessageSquareWarning },
  { to: "/users", label: "Users", icon: Users },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">FF</span>
          <div>
            <strong>FlowForge</strong>
            <small>Order Agent</small>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="eyebrow">Week 3 MVP</span>
            <h1>B2B AI Order Processing Agent</h1>
          </div>
          <span className="mode-pill">Mock integrations enabled</span>
        </header>
        <section className="content-area">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
