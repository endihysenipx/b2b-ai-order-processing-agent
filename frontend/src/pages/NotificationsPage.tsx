import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api/client";
import type { NotificationList, OrderNotification } from "../types/notification";

export function NotificationsPage() {
  const [category, setCategory] = useState("");
  const [unread, setUnread] = useState(false);
  const [demo, setDemo] = useState(false);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<{ key: string; data: NotificationList } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const query = new URLSearchParams({ page: String(page), unread_only: String(unread), include_demo: String(demo),
    ...(category ? { category } : {}) }).toString();
  const data = result?.key === query ? result.data : null;
  const refresh = useCallback(() => setRefreshKey(value => value + 1), []);
  useEffect(() => {
    let active = true;
    let running = false;
    async function load() {
      if (running) return;
      running = true;
      try {
        const next = await apiRequest<NotificationList>(`/notifications?${query}`);
        if (active) { setResult({ key: query, data: next }); setError(""); }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Could not load notifications."); }
      finally { running = false; }
    }
    void load();
    const timer = window.setInterval(() => { if (document.visibilityState !== "hidden") void load(); }, 60000);
    window.addEventListener("focus", load);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", load); };
  }, [query, refreshKey]);

  async function acknowledge(item: OrderNotification) {
    setBusy(item.order_id); setError("");
    try {
      await apiRequest(`/notifications/${item.order_id}/read`, { method: "PUT",
        body: JSON.stringify({ fingerprint: item.fingerprint, is_read: !item.is_read }) });
      window.dispatchEvent(new Event("notifications-changed"));
      refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update notification."); }
    finally { setBusy(""); }
  }

  return <div className="page-stack">
    <div className="section-heading"><h2>Order notifications</h2><button onClick={refresh}>Refresh</button></div>
    <p>Orders needing attention for customers you can access. Read status is personal; it does not approve or resolve an order.
      Resolved orders leave this inbox. Refreshes every minute while open.</p>
    <div className="notification-filters">
      <label>Category<select value={category} onChange={e => { setCategory(e.target.value); setPage(1); }}>
        <option value="">All categories</option><option value="failed">Processing failed</option>
        <option value="duplicate">Duplicates</option><option value="waiting">Customer information needed</option>
        <option value="review">Needs review</option>
      </select></label>
      <label><input type="checkbox" checked={unread} onChange={e => { setUnread(e.target.checked); setPage(1); }} /> Unread only</label>
      <label><input type="checkbox" checked={demo} onChange={e => { setDemo(e.target.checked); setPage(1); }} /> Include demo orders</label>
    </div>
    {error && <p role="alert" className="error-message">{error}</p>}
    {!data && !error && <p>Loading notifications…</p>}
    {data && <>
      <p role="status">{data.unread_count} unread · {data.total} matching orders</p>
      {!data.items.length && <p className="empty-state">No notifications match these filters.</p>}
      {data.items.map(item => <article className={`section-panel notification-card ${item.is_read ? "" : "notification-unread"}`} key={item.order_id}>
        <div className="section-heading"><h3>{item.title}</h3><span>{item.is_read ? "Read" : "Unread"}</span></div>
        <Link to={`/orders/${item.order_id}`}>{item.reference}</Link> · {item.client_name} {item.is_demo && <span className="demo-badge">Demo</span>}
        <p>{item.message}</p><small>{item.status} · Order updated {new Date(item.updated_at).toLocaleString()}</small>
        <div><button disabled={Boolean(busy)} onClick={() => void acknowledge(item)}>{busy === item.order_id ? "Saving…" : item.is_read ? "Mark unread" : "Mark read"}</button></div>
      </article>)}
      <div className="action-row"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
        <span>Page {page} of {Math.max(1, Math.ceil(data.total / data.page_size))}</span>
        <button disabled={page * data.page_size >= data.total} onClick={() => setPage(p => p + 1)}>Next</button></div>
    </>}
  </div>;
}
