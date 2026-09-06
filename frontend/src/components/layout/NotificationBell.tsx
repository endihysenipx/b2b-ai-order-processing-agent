import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Bell } from "lucide-react";
import { apiRequest } from "../../api/client";
import type { NotificationList } from "../../types/notification";

export function NotificationBell() {
  const { pathname } = useLocation();
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    let running = false;
    async function refresh() {
      if (running || document.visibilityState === "hidden") return;
      running = true;
      try {
        const data = await apiRequest<NotificationList>("/notifications?page_size=1");
        if (active) { setCount(data.unread_count); setFailed(false); }
      } catch { if (active) setFailed(true); }
      finally { running = false; }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60000);
    window.addEventListener("focus", refresh);
    window.addEventListener("notifications-changed", refresh);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", refresh);
      window.removeEventListener("notifications-changed", refresh); };
  }, [pathname]);
  return <Link to="/notifications" className="notification-bell" aria-label={failed ? "Notifications unavailable" : `Notifications${count === null ? "" : `, ${count} unread`}`}>
    <Bell size={18} aria-hidden="true" /> Notifications
    <span aria-live="polite">{failed ? "!" : count === null ? "…" : count}</span>
  </Link>;
}
