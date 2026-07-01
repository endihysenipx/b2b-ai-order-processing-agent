import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import type { Client } from "../types/client";
import type { OrderListResponse } from "../types/order";

const statuses = ["All", "OK", "Human in the Loop", "Waiting for Reply", "Failed", "ERP Ready", "XMLs Sent", "Rejected"];

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListResponse | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("All");
  const [clientId, setClientId] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "10" });
    if (status !== "All") params.set("status", status);
    if (clientId) params.set("client_id", clientId);
    if (search) params.set("search", search);
    return params.toString();
  }, [clientId, page, search, status]);

  useEffect(() => {
    apiRequest<Client[]>("/clients").then(setClients).catch(() => setClients([]));
  }, []);

  useEffect(() => {
    apiRequest<OrderListResponse>(`/orders?${query}`)
      .then(setOrders)
      .catch((error) => setError(error instanceof Error ? error.message : "Could not load orders"));
  }, [query]);

  return (
    <div className="page-stack">
      <div className="toolbar">
        <input placeholder="Search ticket, commission, customer" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select value={clientId} onChange={(event) => setClientId(event.target.value)}>
          <option value="">All clients</option>
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.client_name}
            </option>
          ))}
        </select>
      </div>
      <div className="status-tabs">
        {statuses.map((item) => (
          <button key={item} className={status === item ? "tab active" : "tab"} onClick={() => setStatus(item)}>
            {item}
          </button>
        ))}
      </div>
      {error && <p className="error-message">{error}</p>}
      {!orders ? (
        <p className="loading">Loading orders...</p>
      ) : orders.items.length === 0 ? (
        <p className="empty-state">No orders match the current filters.</p>
      ) : (
        <section className="section-panel">
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Ticket</th>
                <th>Commission</th>
                <th>Client</th>
                <th>Received</th>
                <th>Delivery Week</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {orders.items.map((order) => (
                <tr key={order.id}>
                  <td>{order.id.slice(0, 8)}</td>
                  <td>{order.ticket_number}</td>
                  <td>{order.commission_number ?? "Missing"}</td>
                  <td>{order.client.client_name}</td>
                  <td>{new Date(order.created_at).toLocaleDateString()}</td>
                  <td>{order.delivery_week}</td>
                  <td>
                    <StatusBadge status={order.status} />
                  </td>
                  <td>
                    <Link className="text-action" to={`/orders/${order.id}`}>
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <button disabled={page === 1} onClick={() => setPage((value) => value - 1)}>
              Previous
            </button>
            <span>
              Page {orders.page} of {Math.max(1, Math.ceil(orders.total / orders.page_size))}
            </span>
            <button disabled={page * orders.page_size >= orders.total} onClick={() => setPage((value) => value + 1)}>
              Next
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
