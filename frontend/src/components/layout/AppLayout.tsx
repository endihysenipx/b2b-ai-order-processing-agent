import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ClipboardList, Database, FileDown, Gauge, MessageSquareWarning, ScanSearch, Settings, Sparkles, Users } from "lucide-react";
import { clearAccessToken, getAuthenticatedUser } from "../../api/client";
import type { User } from "../../types/user";

const navItems = [
  { to: "/", label: "Overview", icon: Gauge },
  { to: "/orders", label: "Orders", icon: ClipboardList },
  { to: "/intelligence", label: "Order Intelligence", icon: ScanSearch, adminOnly: true },
  { to: "/demo-data", label: "Demo Data", icon: Sparkles, adminOnly: true },
  { to: "/clients", label: "Clients", icon: Database },
  { to: "/data-export", label: "Data Export", icon: FileDown },
  { to: "/feedback", label: "Feedback & Issues", icon: MessageSquareWarning },
  { to: "/users", label: "Users", icon: Users, adminOnly: true },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppLayout() {
  const navigate = useNavigate();
  const user = getAuthenticatedUser<User>();
  const visibleNavItems = navItems.filter((item) => !item.adminOnly || user?.role === "admin");

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

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
          {visibleNavItems.map((item) => {
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
            <span className="eyebrow">Production operations</span>
            <h1>B2B AI Order Processing Agent</h1>
          </div>
          <div className="session-controls">
            <span>{user?.full_name} · {user?.role}</span>
            <button type="button" onClick={logout}>Log out</button>
          </div>
        </header>
        <section className="content-area">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
