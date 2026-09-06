import { useEffect, useState } from "react";
import type { OrderDetail, OrderItem } from "../../types/order";

export type CatalogProduct = {
  id: string; sku: string; description: string; aliases: string[]; is_active: boolean;
  unit: string; unit_price: string | null; currency: string | null; minimum_quantity: number;
  on_hand: number | null; reserved: number; order_reserved?: number; warehouse: string; stock_updated_at: string | null;
};
export type ItemCorrection = {
  article_number: string | null; model_number: string | null; quantity: number | null;
  unit_price: string | null; total_price?: string | null; currency: string | null;
};

function draftFor(item: OrderItem) {
  return { article_number: item.article_number ?? "", model_number: item.model_number ?? "",
    quantity: item.quantity === null ? "" : String(item.quantity), unit_price: item.unit_price ?? "",
    total_price: item.total_price ?? "", currency: item.currency ?? "" };
}

function computedTotal(quantity: string, price: string) {
  if (!/^\d+$/.test(quantity) || !/^\d+(\.\d{0,2})?$/.test(price)) return null;
  const [whole, fraction = ""] = price.split(".");
  const cents = BigInt(quantity) * (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0")));
  return `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
}

export function OrderItemEditor({ item, number, products, issues, disabled, onDirty, onSave }: {
  item: OrderItem; number: number; products: CatalogProduct[]; issues: OrderDetail["validation_issues"];
  disabled: boolean; onDirty: (id: string, dirty: boolean) => void;
  onSave: (id: string, payload: ItemCorrection) => Promise<OrderItem>;
}) {
  const original = draftFor(item);
  const [draft, setDraft] = useState(original);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);
  const dirty = JSON.stringify(draft) !== JSON.stringify(original);
  const prefix = `items[${number}]`;
  const lineIssues = issues.filter(issue => !issue.is_resolved && (issue.field_name === prefix || issue.field_name.startsWith(prefix + ".")));
  const matched = products.find(p => p.sku === draft.article_number.trim() || p.aliases.includes(draft.article_number.trim()));
  const matches = products.filter(p => p.is_active && [p.sku, p.description, ...p.aliases].some(text => text.toLowerCase().includes(search.toLowerCase())));
  const total = computedTotal(draft.quantity, draft.unit_price);
  const totalNeedsCorrection = total !== null && (item.total_price === null || Number(total) !== Number(item.total_price));

  function change(values: Partial<typeof draft>) {
    const next = { ...draft, ...values };
    if ("quantity" in values || "unit_price" in values) next.total_price = "";
    setDraft(next); setError("");
    onDirty(item.id, JSON.stringify(next) !== JSON.stringify(original));
  }

  function fieldIssues(field: string) {
    return lineIssues.filter(issue => issue.field_name === `${prefix}.${field}`);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault(); setError("");
    const payload: ItemCorrection = {
      article_number: draft.article_number.trim() || null, model_number: draft.model_number.trim() || null,
      quantity: draft.quantity === "" ? null : Number(draft.quantity), unit_price: draft.unit_price || null,
      currency: draft.currency.trim().toUpperCase() || null,
      ...(draft.quantity && draft.unit_price ? {} : { total_price: draft.total_price || null }),
    };
    try { const saved = await onSave(item.id, payload); setDraft(draftFor(saved)); onDirty(item.id, false); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save this line."); }
  }

  return <form className="order-line-editor" aria-label={`Edit line ${number}`} id={`order-line-${number}`} onSubmit={save}>
    <fieldset disabled={disabled}>
      <div className="line-compact-row">
        <span className="line-number" title={`Line ${number}`}>{number}</span>
        {([ ["article_number", "Article"], ["model_number", "Model"], ["quantity", "Quantity"], ["unit_price", "Unit price"], ["total_price", "Line total"], ["currency", "Currency"] ] as const).map(([field, label]) => {
          const problems = fieldIssues(field);
          const numeric = ["quantity", "unit_price", "total_price"].includes(field);
          const id = `line-${number}-${field}`;
          return <label key={field} htmlFor={id}>{label}
            <input id={id} aria-label={`${label} for line ${number}`} aria-invalid={problems.length > 0} aria-describedby={problems.length ? `${id}-issues` : undefined}
              type={numeric ? "number" : "text"} min={numeric ? field === "quantity" ? "1" : "0" : undefined}
              max={numeric ? field === "quantity" ? "2147483647" : "9999999999.99" : undefined}
              step={numeric ? field === "quantity" ? "1" : "0.01" : undefined}
              maxLength={field === "currency" ? 3 : 100}
              readOnly={field === "total_price" && total !== null}
              value={field === "total_price" && total !== null ? total : draft[field]}
              onChange={e => change({ [field]: field === "currency" ? e.target.value.toUpperCase() : e.target.value })} />
            {problems.length > 0 && <span id={`${id}-issues`} className="error-message">{problems.map(p => p.message).join(" ")}</span>}
          </label>;
        })}
        <div className="line-row-actions"><button type="submit" aria-label={`Save line ${number}`} disabled={!dirty && !totalNeedsCorrection}>Save</button>
          <button type="button" aria-label={`Cancel line ${number} changes`} disabled={!dirty} onClick={() => { setDraft(original); setError(""); onDirty(item.id, false); }}>Cancel</button>
        </div>
      </div>
      {totalNeedsCorrection && <p>Saved total: {item.total_price ?? "Missing"}. Save this line to use the calculated total shown above.</p>}
      {lineIssues.filter(issue => issue.field_name === prefix).map(issue => <p className="error-message" key={issue.id}>{issue.message}</p>)}
      {error && <p role="alert" className="error-message">{error}</p>}
      <details className="line-catalog-details"><summary>Catalog & stock{matched ? ` · ${matched.on_hand === null ? "Unknown stock" : `${matched.on_hand - matched.reserved - (matched.order_reserved ?? 0)} available`}` : " · Find product"}{dirty ? " · Unsaved changes" : ""}</summary>
      <div className="order-form-grid">
        <label>Search catalog<input aria-label={`Search catalog for line ${number}`} value={search} placeholder="SKU, product name or customer alias" onChange={e => setSearch(e.target.value)} /></label>
        <label>Select matching product<select aria-label={`Catalog match for line ${number}`} value="" onChange={e => {
          const product = products.find(p => p.id === e.target.value);
          if (product) change({ article_number: product.sku });
        }}><option value="">Choose a product…</option>{matches.slice(0, 25).map(p => <option key={p.id} value={p.id}>{p.sku} — {p.description}</option>)}</select></label>
      </div>
      {matches.length > 25 && <p>Showing 25 of {matches.length} matches. Refine your search.</p>}
      {products.length > 0 && matches.length === 0 && <p>No active catalog matches. You can correct the article manually.</p>}
      {matched && <div className="catalog-match">
        <strong>{matched.sku} — {matched.description}</strong>
        <p>{matched.is_active ? "Active" : "Inactive"} · Unit: {matched.unit} · Minimum: {matched.minimum_quantity} · Available: {matched.on_hand === null ? "Unknown" : matched.on_hand - matched.reserved - (matched.order_reserved ?? 0)} at {matched.warehouse}</p>
        <p>Stock observed: {matched.stock_updated_at ? new Date(matched.stock_updated_at).toLocaleString() : "Unknown"}
          {matched.stock_updated_at && now - new Date(matched.stock_updated_at).getTime() > 86400000 && " — stale (over 24 hours)"}</p>
        {matched.unit_price !== null && <p>Agreed price: {matched.unit_price} {matched.currency} <button type="button" onClick={() => change({ unit_price: matched.unit_price!, currency: matched.currency ?? "" })}>Use agreed price for line {number}</button></p>}
      </div>}
        <small>Totals calculate from quantity × unit price. Saving reruns validation.</small>
      </details>
    </fieldset>
  </form>;
}
