import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiRequest, getAuthenticatedUser } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import { ClarificationDraft } from "../components/orders/ClarificationDraft";
import { OrderItemEditor, type CatalogProduct, type ItemCorrection } from "../components/orders/OrderItemEditor";
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
  const { orderId } = useParams();
  return <OrderDetailsContent key={orderId} orderId={orderId} />;
}

function OrderDetailsContent({ orderId }: { orderId?: string }) {
  const isAdmin = getAuthenticatedUser<User>()?.role === "admin";
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [headerDirty, setHeaderDirty] = useState(false);
  const [dirtyLines, setDirtyLines] = useState<Set<string>>(new Set());
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const [catalogLoading, setCatalogLoading] = useState(true);
  const clientId = order?.client.id;
  const reservationKey = JSON.stringify(order?.stock_reservations ?? []);
  const hasDuplicates = Boolean(order?.duplicate_orders?.length);
  const hasDrafts = headerDirty || dirtyLines.size > 0;

  useEffect(() => {
    if (!clientId) return;
    let active = true;
    apiRequest<CatalogProduct[]>(`/clients/${clientId}/products`).then(data => {
      if (active) {
        if (Array.isArray(data)) setProducts(data);
        else setCatalogError("Catalog could not be loaded. Manual corrections are still available.");
      }
    }).catch(e => { if (active) setCatalogError(String(e)); })
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, [clientId, reservationKey]);

  useEffect(() => {
    if (!hasDrafts) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasDrafts]);

  function lineDirty(id: string, dirty: boolean) {
    setDirtyLines(previous => { const next = new Set(previous); if (dirty) next.add(id); else next.delete(id); return next; });
  }

  function headerIssues(field: string) {
    const issues = order?.validation_issues.filter(issue => !issue.is_resolved && (issue.issue_type !== "duplicate_order" || hasDuplicates) && issue.field_name === field) ?? [];
    return issues.length ? <span className="error-message">{issues.map(issue => issue.message).join(" ")}</span> : null;
  }

  const loadOrder = useCallback(() => {
    if (!orderId) return;
    return apiRequest<OrderDetail>(`/orders/${orderId}`)
      .then(setOrder)
      .catch((error) => setError(error instanceof Error ? error.message : "Could not load order"));
  }, [orderId]);

  useEffect(() => { void loadOrder(); }, [loadOrder]);

  async function saveHeader(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!order) return;
    const formData = new FormData(event.currentTarget);
    setBusy(true); setError(""); setMessage("");
    try {
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
      setHeaderDirty(false);
      setMessage("Corrections saved and validation refreshed.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save corrections."); }
    finally { setBusy(false); }
  }

  async function saveItem(itemId: string, payload: ItemCorrection) {
    if (!order) throw new Error("Order has not loaded.");
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await apiRequest<OrderDetail>(`/orders/${order.id}/items/${itemId}`, {
        method: "PATCH", body: JSON.stringify(payload),
      });
      setOrder(updated); lineDirty(itemId, false);
      setMessage("Line saved and validation refreshed. Approval and generated XML were cleared.");
      return updated.items.find(item => item.id === itemId)!;
    } finally { setBusy(false); }
  }

  async function action(path: string, success: string) {
    if (!order) return;
    if (busy || hasDrafts) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest<OrderDetail | { message: string }>(`/orders/${order.id}/${path}`, {
        method: "POST",
      });
      setMessage("message" in result ? result.message : success);
      await loadOrder();
    } catch (error) {
      setError(error instanceof Error ? error.message : "The order action failed");
      await loadOrder();
    } finally { setBusy(false); }
  }

  if (error && !order) return <p className="error-message">{error}</p>;
  if (!order) return <p className="loading">Loading order details...</p>;

  return (
    <div className="page-stack">
      <div className="detail-heading">
        <div>
          <span className="eyebrow">Order {order.id.slice(0, 8)}</span>
          <h2>{order.ticket_number} {order.is_demo && <span className="demo-badge">Demo data</span>}</h2>
        </div>
        <Link to={`/history?order_id=${encodeURIComponent(order.id)}`}>View change history</Link>
        <StatusBadge status={order.status} />
      </div>
      {error && <p role="alert" className="error-message">{error}</p>}
      {hasDuplicates && <section className="section-panel" role="alert">
        <h3>Possible duplicate order</h3>
        <p>This customer's PO / commission number appears on another order. Approval and XML export are blocked.
          Compare the orders, then correct the reference or reject the extra order. Refresh after resolving another order.</p>
        <ul>{order.duplicate_orders?.map(match => <li key={match.id}>
          <Link to={`/orders/${match.id}`}>{match.commission_number} — {match.ticket_number || match.id}</Link>
          {" — "}{match.status}{" — "}{new Date(match.created_at).toLocaleString()}
        </li>)}</ul>
        <button onClick={() => void loadOrder()} disabled={busy || hasDrafts}>Refresh duplicate check</button>
      </section>}
      {message && <p className="success-message">{message}</p>}
      {hasDrafts && <p role="status">Save or cancel your corrections before validating, approving, or exporting this order.</p>}
      <section className="detail-grid">
        <form aria-label="Header corrections" className="section-panel edit-form" onSubmit={saveHeader} onChange={() => setHeaderDirty(true)}>
          <fieldset disabled={busy}>
          <h3>Header Data</h3>
          <div className="order-form-grid">
            <label>
              Ticket number
              <input name="ticket_number" defaultValue={order.ticket_number ?? ""} />
              {headerIssues("ticket_number")}
            </label>
            <label>
              Customer number
              <input name="customer_number" defaultValue={order.customer_number ?? ""} />
              {headerIssues("customer_number")}
            </label>
            <label>
              Customer name
              <input name="customer_name" defaultValue={order.customer_name ?? ""} />
              {headerIssues("customer_name")}
            </label>
            <label>
              Commission number
              <input name="commission_number" defaultValue={order.commission_number ?? ""} />
              {headerIssues("commission_number")}
            </label>
            <label>
              Commission name
              <input name="commission_name" defaultValue={order.commission_name ?? ""} />
              {headerIssues("commission_name")}
            </label>
            <label>
              Delivery week
              <input name="delivery_week" defaultValue={order.delivery_week ?? ""} />
              {headerIssues("delivery_week")}
            </label>
            <label className="field-span-2">
              Store address
              <textarea name="store_address" defaultValue={order.store_address ?? ""} />
              {headerIssues("store_address")}
            </label>
            <label className="field-span-2">
              Delivery address
              <textarea name="delivery_address" defaultValue={order.delivery_address ?? ""} />
              {headerIssues("delivery_address")}
            </label>
            <label>
              Order date
              <input type="date" name="order_date" defaultValue={order.order_date ?? ""} />
              {headerIssues("order_date")}
            </label>
            <label>
              Requested delivery date
              <input type="date" name="requested_delivery_date" defaultValue={order.requested_delivery_date ?? ""} />
              {headerIssues("requested_delivery_date")}
            </label>
            <label>
              Contact person
              <input name="contact_person" defaultValue={order.contact_person ?? ""} />
              {headerIssues("contact_person")}
            </label>
            <label>
              Phone number
              <input name="phone_number" defaultValue={order.phone_number ?? ""} />
              {headerIssues("phone_number")}
            </label>
            <label>
              Total price
              <input type="number" min="0" step="0.01" name="total_price" defaultValue={order.total_price ?? ""} />
              {headerIssues("total_price")}
            </label>
            <label>
              Currency
              <input name="currency" maxLength={10} defaultValue={order.currency ?? ""} />
              {headerIssues("currency")}
            </label>
          </div>
          <div className="action-row"><button type="submit" disabled={!headerDirty}>Save corrections</button>
            <button type="button" disabled={!headerDirty} onClick={e => { e.currentTarget.form?.reset(); setHeaderDirty(false); }}>Cancel header changes</button></div>
          </fieldset>
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
        <h3>Order Items</h3>
        <p>Correct any line below. Selecting a product changes the article in your draft; use the agreed-price button to apply its price.</p>
        {catalogLoading && <p>Loading customer catalog…</p>}
        {catalogError && <p className="error-message">{catalogError}</p>}
        {!catalogLoading && !catalogError && products.length === 0 && <p>No catalog products configured for this customer. Manual corrections are available.</p>}
        {order.items.length === 0 && <p className="empty-state">No line items were extracted. Review the source document before approval.</p>}
        {order.items.map((item, index) => <OrderItemEditor key={`${item.id}:${JSON.stringify(item)}`} item={item} number={index + 1}
          products={products} issues={order.validation_issues} disabled={busy} onDirty={lineDirty} onSave={saveItem} />)}
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
          {order.validation_issues.filter(issue => !issue.is_resolved && (issue.issue_type !== "duplicate_order" || hasDuplicates)).length === 0 ? (
            <p className="empty-state">No open validation issues.</p>
          ) : (
            order.validation_issues.filter(issue => !issue.is_resolved && (issue.issue_type !== "duplicate_order" || hasDuplicates)).map((issue) => (
              <p key={issue.id}>
                <strong>{issue.severity === "error" ? "Needs correction" : "Review"} — {issue.field_name}</strong>: {issue.message}
                {/items\[(\d+)\]/.test(issue.field_name) && <a href={`#order-line-${issue.field_name.match(/items\[(\d+)\]/)?.[1]}`}> Go to line</a>}
              </p>
            ))
          )}
        </div>
      </section>

      <ClarificationDraft orderId={order.id} revision={JSON.stringify(order)} disabled={busy || hasDrafts} />

      <section className="section-panel">
        <h3>XML Status</h3>
        <p>Stock reserved for this order: {order.stock_reservations?.reduce((sum, row) => sum + row.quantity, 0) ?? 0} units.
          Corrections, rejection, or revalidation release unsent allocations; approval reserves them again.</p>
        <fieldset disabled={busy || hasDrafts}><div className="action-row">
          <button onClick={() => action("validate", "Validation refreshed.")}>Validate order</button>
          <button disabled={hasDuplicates} onClick={() => action("approve", "Order approved.")}>Approve</button>
          {isAdmin && <button disabled={hasDuplicates} onClick={() => action("generate-xml", "XML generated.")}>Generate XML</button>}
          {isAdmin && <button disabled={hasDuplicates} onClick={() => action("send-xml", "XML sent.")}>Send XMLs</button>}
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
        </fieldset>
        {order.generated_xmls.map((xml) => (
          <p key={xml.id}>
            {xml.xml_type}: {xml.status} - {xml.file_path}
          </p>
        ))}
      </section>
    </div>
  );
}
