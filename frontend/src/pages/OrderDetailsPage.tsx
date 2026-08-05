import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiRequest, getAuthenticatedUser } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import type { OrderDetail } from "../types/order";
import type { User } from "../types/user";

function optionalFormValue(formData: FormData, name: string) {
  const value = formData.get(name);
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function displayValue(value: string | null) {
  return value || "—";
}

function displayDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

export function OrderDetailsPage() {
  const isAdmin = getAuthenticatedUser<User>()?.role === "admin";
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
        ticket_number: optionalFormValue(formData, "ticket_number"),
        customer_number: optionalFormValue(formData, "customer_number"),
        customer_name: optionalFormValue(formData, "customer_name"),
        commission_number: optionalFormValue(formData, "commission_number"),
        commission_name: optionalFormValue(formData, "commission_name"),
        store_address: optionalFormValue(formData, "store_address"),
        delivery_address: optionalFormValue(formData, "delivery_address"),
        delivery_week: optionalFormValue(formData, "delivery_week"),
        order_date: optionalFormValue(formData, "order_date"),
        requested_delivery_date: optionalFormValue(formData, "requested_delivery_date"),
        contact_person: optionalFormValue(formData, "contact_person"),
        phone_number: optionalFormValue(formData, "phone_number"),
        total_price: optionalFormValue(formData, "total_price"),
        currency: optionalFormValue(formData, "currency")?.toUpperCase() ?? null,
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
    setError("");
    try {
      const result = await apiRequest<OrderDetail | { message: string }>(`/orders/${order.id}/${path}`, {
        method: "POST",
      });
      setMessage("message" in result ? result.message : success);
      loadOrder();
    } catch (error) {
      setError(error instanceof Error ? error.message : "The order action failed");
    }
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
          <div className="order-form-grid">
            <label>
              Ticket number
              <input name="ticket_number" defaultValue={order.ticket_number ?? ""} />
            </label>
            <label>
              Customer number
              <input name="customer_number" defaultValue={order.customer_number ?? ""} />
            </label>
            <label>
              Customer name
              <input name="customer_name" defaultValue={order.customer_name ?? ""} />
            </label>
            <label>
              Commission number
              <input name="commission_number" defaultValue={order.commission_number ?? ""} />
            </label>
            <label>
              Commission name
              <input name="commission_name" defaultValue={order.commission_name ?? ""} />
            </label>
            <label>
              Delivery week
              <input name="delivery_week" defaultValue={order.delivery_week ?? ""} />
            </label>
            <label className="field-span-2">
              Store address
              <textarea name="store_address" defaultValue={order.store_address ?? ""} />
            </label>
            <label className="field-span-2">
              Delivery address
              <textarea name="delivery_address" defaultValue={order.delivery_address ?? ""} />
            </label>
            <label>
              Order date
              <input type="date" name="order_date" defaultValue={order.order_date ?? ""} />
            </label>
            <label>
              Requested delivery date
              <input type="date" name="requested_delivery_date" defaultValue={order.requested_delivery_date ?? ""} />
            </label>
            <label>
              Contact person
              <input name="contact_person" defaultValue={order.contact_person ?? ""} />
            </label>
            <label>
              Phone number
              <input name="phone_number" defaultValue={order.phone_number ?? ""} />
            </label>
            <label>
              Total price
              <input type="number" min="0" step="0.01" name="total_price" defaultValue={order.total_price ?? ""} />
            </label>
            <label>
              Currency
              <input name="currency" maxLength={10} defaultValue={order.currency ?? ""} />
            </label>
          </div>
          <button type="submit">Save corrections</button>
        </form>
        <section className="section-panel">
          <h3>Client and Email</h3>
          <dl className="metadata-list">
            <dt>Client</dt>
            <dd>{order.client.client_name}</dd>
            <dt>Customer number</dt>
            <dd>{displayValue(order.customer_number)}</dd>
            <dt>Sender</dt>
            <dd>{order.email.sender_email}</dd>
            <dt>Reply To</dt>
            <dd>{displayValue(order.email.reply_to_email)}</dd>
            <dt>Subject</dt>
            <dd>{order.email.subject}</dd>
            <dt>Mail To</dt>
            <dd>{displayValue(order.email.mail_to_email)}</dd>
            <dt>Received</dt>
            <dd>{displayDateTime(order.email.received_at)}</dd>
            <dt>Classification</dt>
            <dd>{order.email.classification_status}</dd>
            <dt>Approved</dt>
            <dd>{displayDateTime(order.approved_at)}</dd>
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
              <th>Currency</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.id}>
                <td>{displayValue(item.article_number)}</td>
                <td>{displayValue(item.model_number)}</td>
                <td>{item.quantity ?? "—"}</td>
                <td>{displayValue(item.unit_price)}</td>
                <td>{displayValue(item.total_price)}</td>
                <td>{displayValue(item.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="detail-grid">
        <div className="section-panel">
          <h3>Attachments</h3>
          {order.attachments.length === 0 ? (
            <p className="empty-state">No attachments.</p>
          ) : (
            order.attachments.map((attachment) => (
              <article className="attachment-card" key={attachment.id}>
                <div className="section-heading">
                  <strong>
                    {attachment.file_name} {attachment.is_scanned ? "(scanned)" : ""}
                  </strong>
                  <span className={`processing-status processing-${attachment.processing_status}`}>
                    {attachment.processing_status.replaceAll("_", " ")}
                  </span>
                </div>
                {attachment.processing_error && <p className="error-message">{attachment.processing_error}</p>}
                {attachment.extracted_text && (
                  <details>
                    <summary>View extracted text</summary>
                    <pre>{attachment.extracted_text}</pre>
                  </details>
                )}
              </article>
            ))
          )}
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
          {isAdmin && <button onClick={() => action("generate-xml", "XML generated.")}>Generate XML</button>}
          {isAdmin && <button onClick={() => action("send-xml", "XML sent.")}>Send XMLs</button>}
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
