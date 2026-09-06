import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest, getAuthenticatedUser } from "../api/client";
import type { Client } from "../types/client";
import { CatalogImport } from "../components/CatalogImport";
import type { User } from "../types/user";

type Customer = Client & { contact_name?: string | null; phone?: string | null; approved_delivery_addresses?: string[]; master_data_enabled?: boolean };
type Product = { id: string; sku: string; description: string; unit: string; aliases: string[]; is_active: boolean; unit_price: string | null; currency: string | null; minimum_quantity: number; warehouse: string; on_hand: number | null; reserved: number; order_reserved?: number; stock_updated_at: string | null };
const blank = { sku: "", description: "", unit: "each", aliases: "", is_active: true, unit_price: "", currency: "", minimum_quantity: "1", warehouse: "Main", on_hand: "", reserved: "0", stock_updated_at: "" };

export function MasterDataPage() {
  const admin = getAuthenticatedUser<User>()?.role === "admin";
  const [clients, setClients] = useState<Customer[]>([]);
  const [clientId, setClientId] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [addresses, setAddresses] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  useEffect(() => { apiRequest<Customer[]>("/clients").then(data => { setClients(data); setClientId(data[0]?.id ?? ""); }).catch(e => setError(String(e))); }, []);
  useEffect(() => {
    let active = true;

    if (!clientId) return;

    Promise.all([apiRequest<Customer>(`/clients/${clientId}`), apiRequest<Product[]>(`/clients/${clientId}/products`)])
      .then(([c, p]) => { if (active) { setCustomer(c); setAddresses((c.approved_delivery_addresses ?? []).join("\n")); setProducts(p); } })
      .catch(e => { if (active) setError(String(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [clientId]);
  async function saveCustomer(event: React.FormEvent) {
    event.preventDefault(); if (!customer) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await apiRequest<Customer>(`/clients/${clientId}/customer-data`, { method: "PUT", body: JSON.stringify({ contact_name: customer.contact_name || null, phone: customer.phone || null, approved_delivery_addresses: addresses.split("\n").map(a => a.trim()).filter(Boolean), is_active: customer.is_active, master_data_enabled: customer.master_data_enabled ?? false }) });
      setCustomer(saved); setNotice("Customer details saved.");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function saveProduct(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest(`/clients/${clientId}/products${editing ? `/${editing}` : ""}`, { method: editing ? "PUT" : "POST", body: JSON.stringify({ ...form, aliases: form.aliases.split(",").map(a => a.trim()).filter(Boolean), unit_price: form.unit_price || null, currency: form.currency || null, minimum_quantity: Number(form.minimum_quantity), on_hand: form.on_hand === "" ? null : Number(form.on_hand), reserved: Number(form.reserved), stock_updated_at: form.stock_updated_at ? new Date(form.stock_updated_at).toISOString() : null }) });
      setProducts(await apiRequest<Product[]>(`/clients/${clientId}/products`)); setForm(blank); setEditing(""); setNotice("Product saved.");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  function edit(p: Product) {
    setEditing(p.id);
    setForm({ sku: p.sku, description: p.description, unit: p.unit, aliases: p.aliases.join(", "), is_active: p.is_active, unit_price: p.unit_price ?? "", currency: p.currency ?? "", minimum_quantity: String(p.minimum_quantity), warehouse: p.warehouse, on_hand: p.on_hand === null ? "" : String(p.on_hand), reserved: String(p.reserved), stock_updated_at: p.stock_updated_at ? new Date(p.stock_updated_at).toISOString() : "" });
  }
  return <div className="master-data-page">
    <section className="section-panel"><h2>Customer & product data</h2>
      <label>Customer <select value={clientId} disabled={busy || importBusy} onChange={e => { setClientId(e.target.value); setCustomer(null); setProducts([]); setEditing(""); setForm(blank); setError(""); setNotice(""); setLoading(true); }}>{clients.map(c => <option key={c.id} value={c.id}>{c.client_name}</option>)}</select></label>
      {clientId && <Link to={`/history?client_id=${encodeURIComponent(clientId)}`}>View customer change history</Link>}
      {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}{loading && <p>Loading customer data…</p>}
      {!clients.length && <p>No customers available.</p>}
    </section>
    {customer && admin && <CatalogImport key={clientId} clientId={clientId} disabled={busy} onBusyChange={setImportBusy} onImported={() => {
      apiRequest<Product[]>(`/clients/${clientId}/products`).then(setProducts).catch(e => setError(String(e)));
      setEditing(""); setForm(blank);
    }} />}
    {customer && <div className="detail-grid"><section className="section-panel"><h2>Customer details</h2>
      <form onSubmit={saveCustomer}><fieldset disabled={!admin || busy || importBusy}>
        <label>Contact name<input value={customer.contact_name ?? ""} maxLength={200} onChange={e => setCustomer({ ...customer, contact_name: e.target.value })} /></label>
        <label>Phone<input value={customer.phone ?? ""} maxLength={50} onChange={e => setCustomer({ ...customer, phone: e.target.value })} /></label>
        <label>Approved delivery addresses (one per line)<textarea value={addresses} onChange={e => setAddresses(e.target.value)} /></label>
        <label><input type="checkbox" checked={customer.is_active} onChange={e => setCustomer({ ...customer, is_active: e.target.checked })} />Active account</label>
        <label><input type="checkbox" checked={customer.master_data_enabled ?? false} onChange={e => setCustomer({ ...customer, master_data_enabled: e.target.checked })} />Enable catalog, address, stock and pricing checks</label>
        <p>Enable after entering the catalog and approved addresses. Stock older than 24 hours requires review. Stock is a snapshot of availability allocated to this customer; orders do not reserve it.</p>
        {admin && <button type="submit">Save customer</button>}
      </fieldset></form>
    </section><section className="section-panel"><h2>Products & availability</h2>
      {!products.length ? <p>No products configured.</p> : <table><thead><tr><th>SKU / product</th><th>Available</th><th>Reserved by orders</th><th>Price</th><th>Stock updated (UTC)</th>{admin && <th>Edit</th>}<th>History</th></tr></thead><tbody>{products.map(p => <tr key={p.id}><td>{p.sku} — {p.description}{!p.is_active && " (inactive)"}<small> {p.unit} · {p.warehouse}</small></td><td>{p.on_hand === null ? "Unknown" : p.on_hand - p.reserved - (p.order_reserved ?? 0)}</td><td>{p.order_reserved ?? 0}</td><td>{p.unit_price ?? "—"} {p.currency}</td><td>{p.stock_updated_at ?? "Unknown"}</td>{admin && <td><button disabled={busy || importBusy} onClick={() => edit(p)}>Edit</button></td>}<td><Link to={`/history?client_id=${encodeURIComponent(clientId)}&entity_type=product&entity_id=${encodeURIComponent(p.id)}`}>History</Link></td></tr>)}</tbody></table>}
      {admin && <form onSubmit={saveProduct}><h3>{editing ? "Edit product" : "Add product"}</h3><fieldset disabled={busy || importBusy}>
        {([ ["sku", "SKU"], ["description", "Description"], ["unit", "Unit"], ["aliases", "Customer article aliases (comma separated)"], ["unit_price", "Agreed unit price (optional)"], ["currency", "Currency (e.g. EUR)"], ["minimum_quantity", "Minimum quantity"], ["warehouse", "Warehouse"], ["on_hand", "On-hand quantity (blank = unknown)"], ["reserved", "Reserved outside this app"], ["stock_updated_at", "Stock observed at (ISO date with timezone)"] ] as const).map(([key, label]) => <label key={key}>{label}<input required={["sku", "description", "unit", "minimum_quantity", "warehouse", "reserved"].includes(key)} value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}
        <label><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />Active product</label>
        <button type="submit">Save product</button> <button type="button" onClick={() => { setEditing(""); setForm(blank); }}>Clear form</button>
      </fieldset></form>}
    </section></div>}
  </div>;
}
