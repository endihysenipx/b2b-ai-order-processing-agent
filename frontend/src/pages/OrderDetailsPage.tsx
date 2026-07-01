import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import type { OrderDetail } from "../types/order";

export function OrderDetailsPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function loadOrder() {
    if (!orderId) return;
    apiRequest<OrderDetail>(`/orders/${orderId}`)
      .then(setOrder)
      .catch((error) => setError(error instanceof Error ? error.message : "Could not load order"));
  }

  useEffect(loadOrder, [orderId]);

  async function saveHeader(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!order) return;
    const formData = new FormData(event.currentTarget);
    const updated = await apiRequest<OrderDetail>(`/orders/${order.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        ticket_number: formData.get("ticket_number"),
        commission_number: formData.get("commission_number"),
        delivery_address: formData.get("delivery_address"),
      }),
    });
    setOrder(updated);
    setMessage("Corrections saved.");
  }

  async function saveFirstItem() {
    if (!order || !order.items[0]) return;
    const item = order.items[0];
    const updated = await apiRequest<OrderDetail>(`/orders/${order.id}/items/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity: (item.quantity ?? 0) + 1 }),
    });
    setOrder(updated);
    setMessage("First item quantity updated.");
  }

  async function action(path: string, success: string) {
    if (!order) return;
    const result = await apiRequest<OrderDetail | { message: string }>(`/orders/${order.id}/${path}`, { method: "POST" });
    setMessage("message" in result ? result.message : success);
    loadOrder();
  }

  if (error) return <p className="error-message">{error}</p>;
  if (!order) return <p className="loading">Loading order details...</p>;

  return (
    <div className="page-stack">
      <div className="detail-heading">
        <div>
          <span className="eyebrow">Order {order.id.slice(0, 8)}</span>
          <h2>{order.ticket_number}</h2>
        </div>
        <StatusBadge status={order.status} />
      </div>
      {message && <p className="success-message">{message}</p>}
      <section className="detail-grid">
        <form className="section-panel edit-form" onSubmit={saveHeader}>
          <h3>Header Data</h3>
          <label>
            Ticket number
            <input name="ticket_number" defaultValue={order.ticket_number ?? ""} />
          </label>
          <label>
            Commission number
            <input name="commission_number" defaultValue={order.commission_number ?? ""} />
          </label>
          <label>
            Delivery address
            <textarea name="delivery_address" defaultValue={order.delivery_address ?? ""} />
          </label>
          <button type="submit">Save corrections</button>
        </form>
        <section className="section-panel">
          <h3>Client and Email</h3>
          <dl>
            <dt>Client</dt>
            <dd>{order.client.client_name}</dd>
            <dt>Sender</dt>
            <dd>{order.email.sender_email}</dd>
            <dt>Subject</dt>
            <dd>{order.email.subject}</dd>
            <dt>Mail To</dt>
            <dd>{order.email.mail_to_email}</dd>
          </dl>
        </section>
      </section>

      <section className="section-panel">
        <div className="section-heading">
          <h3>Order Items</h3>
          <button onClick={saveFirstItem}>Edit first item quantity</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Article</th>
              <th>Model</th>
              <th>Quantity</th>
              <th>Unit Price</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.id}>
                <td>{item.article_number}</td>
                <td>{item.model_number}</td>
                <td>{item.quantity}</td>
                <td>{item.unit_price}</td>
                <td>{item.total_price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="detail-grid">
        <div className="section-panel">
          <h3>Attachments</h3>
          {order.attachments.map((attachment) => (
            <p key={attachment.id}>
              {attachment.file_name} {attachment.is_scanned ? "(scanned)" : ""}
            </p>
          ))}
        </div>
        <div className="section-panel">
          <h3>Validation Issues</h3>
          {order.validation_issues.length === 0 ? (
            <p className="empty-state">No open validation issues.</p>
          ) : (
            order.validation_issues.map((issue) => (
              <p key={issue.id}>
                <strong>{issue.field_name}</strong>: {issue.message}
              </p>
            ))
          )}
        </div>
      </section>

      <section className="section-panel">
        <h3>XML Status</h3>
        <div className="action-row">
          <button onClick={() => action("approve", "Order approved.")}>Approve</button>
          <button onClick={() => action("generate-xml", "XML generated.")}>Generate XML</button>
          <button onClick={() => action("send-xml", "XML sent.")}>Send XMLs</button>
          <button
            onClick={() =>
              apiRequest(`/orders/${order.id}/reject`, { method: "POST", body: JSON.stringify({ reason: "Rejected during review" }) }).then(loadOrder)
            }
          >
            Reject
          </button>
          <button
            onClick={() =>
              apiRequest(`/orders/${order.id}/report-issue`, {
                method: "POST",
                body: JSON.stringify({ category: "extraction", title: "Review requested", description: "Operator reported an extraction issue." }),
              }).then(() => setMessage("Issue reported."))
            }
          >
            Report issue
          </button>
        </div>
        {order.generated_xmls.map((xml) => (
          <p key={xml.id}>
            {xml.xml_type}: {xml.status} - {xml.file_path}
          </p>
        ))}
      </section>
    </div>
  );
}
