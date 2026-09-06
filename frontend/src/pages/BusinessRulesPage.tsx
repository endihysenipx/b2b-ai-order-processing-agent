import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { SlidersHorizontal, Truck, BadgePercent, ShieldCheck, ShoppingBag } from "lucide-react";

import { apiRequest, getAuthenticatedUser } from "../api/client";
import { CommercialTerms } from "../components/orders/CommercialTerms";
import type { BusinessRules, ClientCase, ClientRules, CommercialTerms as Terms } from "../types/businessRules";
import type { User } from "../types/user";

type Source = { id: string; subject: string; received_at: string; converted: boolean; order_count: number };
const messageOf = (error: unknown) => error instanceof Error ? error.message : "Request failed";

export function BusinessRulesPage() {
  const [clients, setClients] = useState<ClientRules[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [cases, setCases] = useState<ClientCase[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const admin = getAuthenticatedUser<User>()?.role === "admin";
  const load = useCallback(async () => {
    const [rules, examples] = await Promise.all([apiRequest<ClientRules[]>("/business-rules"), apiRequest<ClientCase[]>("/business-rules/cases")]);
    setClients(rules); setCases(examples);
    setSelectedId(previous => previous || rules[0]?.client_id || "");
  }, []);
  useEffect(() => { void Promise.resolve().then(load).catch(e => setError(messageOf(e))).finally(() => setLoading(false)); }, [load]);
  const selected = clients.find(client => client.client_id === selectedId);

  return <div className="page-stack business-rules-page">
    <section className="section-panel rules-hero">
      <div><span className="eyebrow">Client agreements</span><h2><SlidersHorizontal size={25} /> Business rules</h2>
        <p>Turn each client's terms into predictable order decisions. Edit a rule, test the numbers, and see what changes.</p></div>
      <div className="rules-count"><strong>{clients.length}</strong><span>client profiles</span><strong>{cases.length}</strong><span>editable cases</span></div>
    </section>
    {error && <p role="alert" className="error-message">{error}</p>}
    {loading ? <p>Loading client rules…</p> : !selected ? <p>No client profiles are available.</p> : <>
      <label className="rules-client">Client profile<select value={selectedId} onChange={e => setSelectedId(e.target.value)}>
        {clients.map(client => <option key={client.client_id} value={client.client_id}>{client.client_name}{!client.is_active ? " (inactive)" : ""}</option>)}
      </select></label>
      <RulesEditor key={selected.client_id} client={selected} admin={admin} onSaved={load} />
      <section className="section-panel"><h3>Cases for {selected.client_name}</h3>
        <p>Edit an order's line quantities or prices to try either side of a rule's threshold.</p>
        <div className="rules-cases">{cases.filter(example => example.client_id === selectedId).map(example => <article className="rule-case" key={example.id}>
          <span className="eyebrow">Edited source case</span><h4>{example.label}</h4><p>{example.status}</p>
          <CommercialTerms terms={example.commercial_terms} /><Link to={`/orders/${example.id}`}>Open and edit case →</Link>
        </article>)}</div>
        {!cases.some(example => example.client_id === selectedId) && <p className="empty-state">No case assigned to this client yet.</p>}
      </section>
      {admin && selected.is_active && <CaseCreator key={selectedId} client={selected} onCreated={load} />}
    </>}
  </div>;
}

function RulesEditor({ client, admin, onSaved }: { client: ClientRules; admin: boolean; onSaved: () => Promise<void> }) {
  const [rules, setRules] = useState<BusinessRules>(client.rules);
  const [subtotal, setSubtotal] = useState("420");
  const [preview, setPreview] = useState<Terms | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const change = <K extends keyof BusinessRules>(key: K, value: BusinessRules[K]) => {
    setRules(previous => ({ ...previous, [key]: value })); setDirty(true); setMessage("");
  };
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setPreview(null); setPreviewError("");
      void apiRequest<Terms>("/business-rules/preview", { method: "POST", body: JSON.stringify({ rules, subtotal }) })
        .then(result => { if (active) setPreview(result); })
        .catch(e => { if (active) setPreviewError(messageOf(e)); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [rules, subtotal]);

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiRequest<{ updated_orders: number }>(`/business-rules/clients/${client.client_id}`, { method: "PUT", body: JSON.stringify(rules) });
      setDirty(false); setMessage(`Rules saved. ${result.updated_orders} unsent order(s) recalculated.`); await onSaved();
    } catch (e) { setError(messageOf(e)); } finally { setBusy(false); }
  }
  const number = (key: keyof BusinessRules, label: string, max = "99999999") => <label>{label}<input type="number" min="0" max={max} step="0.01" required value={String(rules[key])} onChange={e => change(key, e.target.value)} /></label>;
  return <div className="rules-workbench">
    <form className="section-panel" onSubmit={save}>
      <h3>Commercial terms</h3><p>Thresholds use the merchandise subtotal before discount and freight. Review uses the final total. Taxes are not calculated.</p>
      <fieldset disabled={!admin || busy}>
        <label>Currency<input value={rules.currency} pattern="[A-Z]{3}" maxLength={3} required onChange={e => change("currency", e.target.value.toUpperCase())} /></label>
        <div className="rule-card"><h4><Truck size={19} /> Freight charge</h4>
          <label className="rule-toggle"><input type="checkbox" checked={rules.freight_enabled} onChange={e => change("freight_enabled", e.target.checked)} /> Charge freight below the free-shipping threshold</label>
          {rules.freight_enabled && <div className="rule-fields">{number("freight_below", "Free freight from")}{number("freight_charge", "Freight charge")}</div>}
        </div>
        <div className="rule-card"><h4><BadgePercent size={19} /> Volume discount</h4>
          <label className="rule-toggle"><input type="checkbox" checked={rules.discount_enabled} onChange={e => change("discount_enabled", e.target.checked)} /> Discount orders at or above a threshold</label>
          {rules.discount_enabled && <div className="rule-fields">{number("discount_from", "Discount from")}{number("discount_percent", "Discount (%)", "100")}</div>}
        </div>
        <div className="rule-card"><h4><ShoppingBag size={19} /> Minimum order</h4>
          <label className="rule-toggle"><input type="checkbox" checked={rules.minimum_enabled} onChange={e => change("minimum_enabled", e.target.checked)} /> Block approval below a minimum subtotal</label>
          {rules.minimum_enabled && number("minimum_order", "Minimum merchandise subtotal")}
        </div>
        <div className="rule-card"><h4><ShieldCheck size={19} /> High-value review</h4>
          <label className="rule-toggle"><input type="checkbox" checked={rules.review_enabled} onChange={e => change("review_enabled", e.target.checked)} /> Require approval before XML export</label>
          {rules.review_enabled && number("review_from", "Review final totals from")}
        </div>
        {admin && <><p>Saving recalculates unsent orders and clears their approvals and generated XML. Sent orders keep their agreed terms.</p>
          <button type="submit" disabled={!dirty || busy}>{busy ? "Saving…" : "Save client rules"}</button></>}
      </fieldset>
      {!admin && <p>Administrator access is required to edit rules.</p>}
      {message && <p role="status" className="success-message">{message}</p>}
      {error && <p role="alert" className="error-message">{error}</p>}
    </form>
    <aside className="section-panel rules-preview"><span className="eyebrow">Try a scenario</span><h3>What will this order cost?</h3>
      <label>Merchandise subtotal ({rules.currency})<input type="number" min="0" step="0.01" max="99999999" value={subtotal} onChange={e => setSubtotal(e.target.value)} /></label>
      <p>{dirty ? "Previewing unsaved rules. Save to apply them to orders." : "Preview only. This does not create or modify an order."}</p>
      {preview ? <CommercialTerms terms={preview} /> : <p>{previewError || "Calculating…"}</p>}
    </aside>
  </div>;
}

function CaseCreator({ client, onCreated }: { client: ClientRules; onCreated: () => Promise<void> }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState("");
  useEffect(() => { void apiRequest<Source[]>("/business-rules/sources").then(setSources).catch(e => setError(messageOf(e))); }, []);
  async function convert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setBusy(true); setError("");
    try {
      const result = await apiRequest<{ id: string }>("/business-rules/cases", { method: "POST", body: JSON.stringify({
        email_id: data.get("email_id"), client_id: client.client_id, label: data.get("label"), article_number: data.get("article_number"),
        quantity: Number(data.get("quantity")), unit_price: data.get("unit_price"),
      }) });
      setCreated(result.id); setSources(previous => previous.filter(source => source.id !== data.get("email_id"))); await onCreated(); form.reset();
    } catch (e) { setError(messageOf(e)); } finally { setBusy(false); }
  }
  return <details className="section-panel"><summary>Turn a forwarded order into a client case</summary>
    <p>This edits the original imported record, assigns it to {client.client_name}, and replaces its line items with the example below. The change history and original attachments retain the source. The case is labeled as demo data.</p>
    <form onSubmit={convert}><fieldset disabled={busy}>
      <label>Source email<select required name="email_id" defaultValue=""><option value="" disabled>Select a recent forward</option>{sources.filter(s => !s.converted && s.order_count <= 1).map(source => <option value={source.id} key={source.id}>{source.subject} · {new Date(source.received_at + (source.received_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</option>)}</select></label>
      <div className="rule-fields"><label>Case name<input name="label" required maxLength={100} placeholder="Small order with freight" /></label><label>Article number<input name="article_number" required maxLength={100} placeholder="CASE-CHAIR" /></label>
        <label>Quantity<input name="quantity" type="number" min="1" max="10000" required defaultValue="2" /></label><label>Unit price ({client.rules.currency})<input name="unit_price" type="number" min="0" max="99999999" step="0.01" required defaultValue="210" /></label></div>
      <button type="submit">{busy ? "Converting…" : "Convert original into client case"}</button>
    </fieldset></form>{error && <p role="alert" className="error-message">{error}</p>}{created && <p role="status">Case created. <Link to={`/orders/${created}`}>Open case</Link></p>}
  </details>;
}
