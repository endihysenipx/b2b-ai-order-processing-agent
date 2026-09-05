import { useRef, useState } from "react";
import { apiDownload, apiRequest } from "../api/client";

type Values = Record<string, string | number | boolean | string[] | null>;
type ImportRow = {
  row: number; sku: string; action: "create" | "update" | "unchanged";
  errors: string[]; warnings: string[]; before: Values | null; after: Values | null;
};
type Preview = {
  rows: ImportRow[]; can_import: boolean; token: string | null; error_rows: number;
  counts: { create: number; update: number; unchanged: number };
};

function display(value: Values[string] | undefined) {
  if (value === null || value === undefined || value === "") return "Empty";
  if (Array.isArray(value)) return value.join(" | ") || "None";
  return String(value);
}

export function CatalogImport({ clientId, onImported, onBusyChange, disabled = false }: {
  clientId: string; onImported: () => void; onBusyChange: (busy: boolean) => void; disabled?: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const base = `/clients/${clientId}/catalog-import`;

  async function run(action: "preview" | "confirm") {
    if (!file || disabled || busy || (action === "confirm" && (!confirmed || !preview?.token))) return;
    if (file.size > 2 * 1024 * 1024) { setError("File exceeds 2 MB."); return; }
    setBusy(true); onBusyChange(true); setError(""); setMessage("");
    const body = new FormData();
    body.append("file", file);
    try {
      if (action === "preview") {
        setPreview(null); setConfirmed(false);
        setPreview(await apiRequest<Preview>(`${base}/preview`, { method: "POST", body }));
      } else {
        body.append("token", preview!.token!); body.append("confirmed", "true");
        const result = await apiRequest<{ created: number; updated: number; unchanged: number }>(`${base}/confirm`, { method: "POST", body });
        setMessage(`Import complete: ${result.created} added, ${result.updated} updated, ${result.unchanged} unchanged.`);
        setPreview(null); setConfirmed(false); setFile(null);
        if (inputRef.current) inputRef.current.value = "";
        onImported();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed.");
      if (action === "confirm") { setPreview(null); setConfirmed(false); }
    } finally { setBusy(false); onBusyChange(false); }
  }

  async function downloadTemplate() {
    setError("");
    try { await apiDownload(`${base}/template`, "product-import-template.csv"); }
    catch (e) { setError(e instanceof Error ? e.message : "Template download failed."); }
  }

  return <section className="section-panel catalog-import">
    <h2>Import product catalog</h2>
    <p>Upload a CSV or single-sheet Excel (.xlsx) file for the selected customer. Maximum 500 rows and 2 MB.</p>
    <p>Existing SKUs are updated; new SKUs are added. Blank cells preserve existing values. No data is saved until you confirm a valid preview.</p>
    <details><summary>Column guide</summary>
      <p>Use the template headers. SKU is required; description is required for new products. Optional columns: unit, is_active, aliases, unit_price, currency, minimum_quantity, warehouse, on_hand, reserved, stock_updated_at.</p>
      <p>Use | between aliases, a decimal point for prices, true/false for active status, and an ISO timestamp with timezone for stock (for example, 2026-09-05T10:00:00Z). Use your actual observation time.</p>
      <p>CSV must be UTF-8 and comma-separated. In Excel, store SKUs as Text to retain leading zeros, and paste formula results as values. To clear a value, use the product edit form.</p>
    </details>
    <button type="button" disabled={busy || disabled} onClick={downloadTemplate}>Download blank CSV template</button>
    <label>Catalog file<input ref={inputRef} type="file" accept=".csv,.xlsx" disabled={busy || disabled} onChange={e => {
      setFile(e.target.files?.[0] ?? null); setPreview(null); setConfirmed(false); setError(""); setMessage("");
    }} /></label>
    <button type="button" disabled={!file || busy || disabled} onClick={() => run("preview")}>{busy ? "Processing…" : "Preview import"}</button>
    {error && <p className="error-message" role="alert">{error}</p>}
    {message && <p className="success-message" role="status">{message}</p>}
    {preview && <div>
      <h3>Import preview</h3>
      <p>{preview.counts.create} to add · {preview.counts.update} to update · {preview.counts.unchanged} unchanged · {preview.error_rows} rows with errors</p>
      {!preview.can_import && <p role="alert">Nothing will be imported. Fix all errors in the file, then upload and preview it again.</p>}
      <table><thead><tr><th>File row</th><th>SKU</th><th>Action</th><th>Details</th></tr></thead>
        <tbody>{preview.rows.map(row => <tr key={row.row}>
          <td>{row.row}</td><td>{row.sku || "Missing"}</td><td>{row.errors.length ? "Blocked" : row.action}</td>
          <td>{row.errors.map((text, i) => <p className="error-message" key={`e${i}`}>{text}</p>)}
            {row.warnings.map((text, i) => <p key={`w${i}`}>{text}</p>)}
            {row.after && <details><summary>Review values{row.action === "update" ? " and changes" : ""}</summary>
              <table><thead><tr><th>Field</th><th>Current</th><th>After import</th></tr></thead>
                <tbody>{Object.entries(row.after).map(([field, value]) => <tr key={field}>
                  <th>{field}</th><td>{display(row.before?.[field])}</td><td>{display(value)}{row.before && JSON.stringify(row.before[field]) !== JSON.stringify(value) && " (changed)"}</td>
                </tr>)}</tbody>
              </table>
            </details>}
          </td>
        </tr>)}</tbody>
      </table>
      {preview.can_import && <>
        <label><input type="checkbox" disabled={busy || disabled} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed the preview and confirm these catalog changes.</label>
        <button type="button" disabled={!confirmed || busy || disabled || preview.counts.create + preview.counts.update === 0} onClick={() => run("confirm")}>Confirm import</button>
        <p>Preview expires after 15 minutes. Catalog changes require a new preview.</p>
      </>}
    </div>}
  </section>;
}
