import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import type { OrderListResponse } from "../types/order";

interface Summary {
  total_orders: number;
  real_order_count: number;
  demo_order_count: number;
  count_by_status: Record<string, number>;
  count_by_client: Record<string, number>;
  recent_order_count: number;
}

export function OverviewPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [orders, setOrders] = useState<OrderListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiRequest<Summary>("/reports/summary"), apiRequest<OrderListResponse>("/orders?page_size=5")])
      .then(([summaryData, orderData]) => {
        setSummary(summaryData);
        setOrders(orderData);
      })
      .catch((error) => setError(error instanceof Error ? error.message : "Could not load overview"));
  }, []);

  if (error) return <p className="error-message">{error}</p>;
  if (!summary || !orders) return <p className="loading">Loading overview...</p>;

  const kpis = ["OK", "Human in the Loop", "Waiting for Reply", "Failed", "ERP Ready"];

  return (
    <div className="page-stack">
      {summary.demo_order_count > 0 && (
        <div className="demo-notice">
          <strong>Demo dataset active</strong>
          <span>
            {summary.demo_order_count.toLocaleString()} synthetic orders and {summary.real_order_count.toLocaleString()} non-demo
            orders are included in these KPIs.
          </span>
          <Link to="/demo-data">Manage demo data</Link>
        </div>
      )}
      <div className="kpi-grid">
        <article className="kpi-card">
          <span>Total orders</span>
          <strong>{summary.total_orders}</strong>
          <small>{summary.recent_order_count} received in the last 7 days</small>
        </article>
        {kpis.map((status) => {
          const count = summary.count_by_status[status] ?? 0;
          const percent = summary.total_orders ? Math.round((count / summary.total_orders) * 100) : 0;
          return (
            <article className="kpi-card" key={status}>
              <span>{status}</span>
              <strong>{count}</strong>
              <small>{percent}% of orders</small>
            </article>
          );
        })}
      </div>

      <section className="section-panel">
        <div className="section-heading">
          <h2>Recent Orders</h2>
          <Link to="/orders">View all</Link>
        </div>
        <table>
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Client</th>
              <th>Delivery Week</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.items.map((order) => (
              <tr key={order.id}>
                <td>
                  <Link to={`/orders/${order.id}`}>{order.ticket_number}</Link>{" "}
                  {order.is_demo && <span className="demo-badge">Demo</span>}
                </td>
                <td>{order.client.client_name}</td>
                <td>{order.delivery_week}</td>
                <td>
                  <StatusBadge status={order.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
