import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import type { Client } from "../types/client";

type Change = { before: unknown; after: unknown };
type Entry = {
  id: string; created_at: string; actor_id: string; actor_name: string;
  client_id: string; client_name: string; entity_type: string; entity_id: string;
  entity_label: string; order_id: string | null; action: string; batch_id: string | null;
  changes: Record<string, Change>;
};
type History = { items: Entry[]; total: number; page: number; page_size: number };
const actions: Record<string, string> = {
  product_created: "Product created", product_updated: "Product updated", customer_updated: "Customer updated",
  catalog_import: "Catalog import", order_approved: "Order approved", order_rejected: "Order rejected",
  order_corrected: "Order corrected", line_corrected: "Line corrected", order_validated: "Order revalidated",
  approval_cleared_by_correction: "Approval cleared by correction", validation_blocked_action: "Action blocked by validation",
  order_revalidated_after_correction: "Order revalidated after correction", xml_generated: "XML generated", xml_sent: "XML sent",
};

function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map(valueText).join("\n") : "None";
  return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
}

export function ChangeHistoryPage() {
  const [params, setParams] = useSearchParams();
  const [clients, setClients] = useState<Client[]>([]);
  const [clientError, setClientError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const query = params.toString();
  const key = `${query}|${refresh}`;
  const [result, setResult] = useState<{ key: string; data?: History; error?: string } | null>(null);
  const data = result?.key === key ? result.data : undefined;
  const error = result?.key === key ? result.error : undefined;
  const loading = result?.key !== key;

  useEffect(() => {
    let active = true;
    apiRequest<Client[]>("/clients").then(values => { if (active) setClients(values); })
      .catch(() => { if (active) setClientError("Customer filters could not be loaded."); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    apiRequest<History>(`/history${query ? `?${query}` : ""}`).then(values => {
      if (active) setResult({ key, data: values });
    }).catch(e => { if (active) setResult({ key, error: e instanceof Error ? e.message : "History could not be loaded." }); });
    return () => { active = false; };
  }, [query, key]);

  function apply(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = new URLSearchParams(params);
    for (const name of ["client_id", "entity_type", "actor", "date_from", "date_to"]) {
      const value = String(form.get(name) ?? "").trim();
      if (value) next.set(name, value); else next.delete(name);
    }
    next.delete("page");
    setParams(next); setRefresh(value => value + 1);
  }

  function page(number: number) {
    const next = new URLSearchParams(params); next.set("page", String(number)); setParams(next);
  }

  return <div className="page-stack history-page">
    <section className="section-panel">
      <div className="section-heading"><h2>Change History</h2><button onClick={() => setRefresh(value => value + 1)} disabled={loading}>Refresh history</button></div>
      <p>Who changed customer details, products, prices, stock, or order decisions. History starts when tracking is deployed; earlier changes are not reconstructed.</p>
      {(params.has("order_id") || params.has("entity_id") || params.has("batch_id")) && <p>Showing history for a selected record or import batch. <button onClick={() => setParams({})}>Show all accessible history</button></p>}
      {clientError && <p className="error-message">{clientError}</p>}
      <form key={query} onSubmit={apply} className="history-filters">
        <label>Customer<select name="client_id" defaultValue={params.get("client_id") ?? ""}><option value="">All accessible customers</option>
          {clients.map(client => <option key={client.id} value={client.id}>{client.client_name}</option>)}</select></label>
        <label>Record type<select name="entity_type" defaultValue={params.get("entity_type") ?? ""}><option value="">All types</option>
          <option value="customer">Customers</option><option value="product">Products / stock / pricing</option><option value="order">Orders / approvals</option><option value="order_item">Order lines</option></select></label>
        <label>Changed by<input name="actor" maxLength={200} defaultValue={params.get("actor") ?? ""} placeholder="Name" /></label>
        <label>From (UTC date)<input type="date" name="date_from" defaultValue={params.get("date_from") ?? ""} /></label>
        <label>To (UTC date)<input type="date" name="date_to" defaultValue={params.get("date_to") ?? ""} /></label>
        <button type="submit">Apply filters</button>
      </form>
    </section>
    {loading && <p role="status">Loading history…</p>}
    {error && <p role="alert" className="error-message">{error}</p>}
    {data && <section className="section-panel">
      <p>{data.total} change entries. Times are shown in your local timezone.</p>
      {!data.items.length && <p className="empty-state">No changes match these filters.</p>}
      {data.items.map(entry => <article key={entry.id} className="history-entry">
        <div className="section-heading"><h3>{actions[entry.action] ?? entry.action.replaceAll("_", " ")}</h3>
          <time dateTime={entry.created_at} title={entry.created_at}>{new Date(entry.created_at).toLocaleString()}</time></div>
        <p><strong>{entry.actor_name}</strong> · {entry.client_name} · {entry.entity_type.replaceAll("_", " ")}: {entry.entity_label}</p>
        <details><summary>View {Object.keys(entry.changes).length} changed fields</summary>
          <table><thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>
            <tbody>{Object.entries(entry.changes).map(([field, change]) => <tr key={field}><th>{field.replaceAll("_", " ")}</th>
              <td className="history-value">{valueText(change.before)}</td><td className="history-value">{valueText(change.after)}</td></tr>)}</tbody>
          </table>
          <p className="history-identifiers">User ID: {entry.actor_id} · Record ID: {entry.entity_id} · Entry ID: {entry.id}</p>
        </details>
        <div className="action-row">
          {entry.order_id && <Link to={`/orders/${encodeURIComponent(entry.order_id)}`}>Open order</Link>}
          {entry.batch_id && <Link to={`/history?batch_id=${encodeURIComponent(entry.batch_id)}`}>View import batch</Link>}
        </div>
      </article>)}
      <div className="action-row"><button disabled={data.page <= 1} onClick={() => page(data.page - 1)}>Previous page</button>
        <span>Page {data.page} of {Math.max(1, Math.ceil(data.total / data.page_size))}</span>
        <button disabled={data.page * data.page_size >= data.total} onClick={() => page(data.page + 1)}>Next page</button></div>
    </section>}
  </div>;
}
