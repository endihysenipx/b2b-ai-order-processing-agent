import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";

interface DemoDataStatus {
  generated: boolean;
  order_count: number;
  target_order_count: number;
  window_days: number;
  date_from: string | null;
  date_to: string | null;
  client_count: number;
  status_counts: Record<string, number>;
  currency_value_totals: Record<string, string>;
  message: string;
}

function formatMoney(value: string, currency: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(value));
}

export function DemoDataPage() {
  const [status, setStatus] = useState<DemoDataStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function loadStatus() {
    apiRequest<DemoDataStatus>("/demo-data")
      .then(setStatus)
      .catch((error) => setError(error instanceof Error ? error.message : "Could not load demo data status"));
  }

  useEffect(loadStatus, []);

  async function generate() {
    setBusy(true);
    setError("");
    try {
      setStatus(await apiRequest<DemoDataStatus>("/demo-data", { method: "POST" }));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Demo data generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Remove all synthetic demo orders? Existing non-demo orders will remain untouched.")) return;
    setBusy(true);
    setError("");
    try {
      setStatus(
        await apiRequest<DemoDataStatus>("/demo-data", {
          method: "DELETE",
          body: JSON.stringify({ confirmation: "DELETE DEMO DATA" }),
        }),
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : "Demo data deletion failed");
    } finally {
      setBusy(false);
    }
  }

  if (!status) return <p className={error ? "error-message" : "loading"}>{error || "Loading Demo Data Studio..."}</p>;

  const largestStatus = Math.max(1, ...Object.values(status.status_counts));

  return (
    <div className="page-stack">
      <section className="demo-hero">
        <div>
          <span className="eyebrow">Safe presentation environment</span>
          <h2>Demo Data Studio</h2>
          <p>
            Build a realistic 30-day operations history without using customer information. Every generated order is visibly
            marked as demo data and can be removed independently.
          </p>
        </div>
        <div className="demo-actions">
          <button type="button" disabled={busy || status.generated} onClick={generate}>
            {busy ? "Working..." : `Generate ${status.target_order_count.toLocaleString()} orders`}
          </button>
          {status.generated && (
            <button type="button" className="danger-button" disabled={busy} onClick={remove}>
              Remove demo dataset
            </button>
          )}
        </div>
      </section>

      {error && <p className="error-message">{error}</p>}
      <p className={status.generated ? "success-message" : "demo-guidance"}>{status.message}</p>

      <div className="kpi-grid">
        <article className="kpi-card"><span>Synthetic orders</span><strong>{status.order_count.toLocaleString()}</strong><small>Clearly marked and filterable</small></article>
        <article className="kpi-card"><span>Demo clients</span><strong>{status.client_count}</strong><small>Fictional .example identities</small></article>
        <article className="kpi-card"><span>History window</span><strong>{status.window_days} days</strong><small>{status.date_from && status.date_to ? `${status.date_from} to ${status.date_to}` : "Ready to generate"}</small></article>
      </div>

      {status.generated && (
        <div className="demo-grid">
          <section className="section-panel">
            <div className="section-heading"><h3>Workflow mix</h3><Link to="/orders">Explore orders</Link></div>
            <div className="demo-status-list">
              {Object.entries(status.status_counts)
                .sort(([, left], [, right]) => right - left)
                .map(([name, count]) => (
                  <div key={name}>
                    <span>{name}</span><strong>{count.toLocaleString()}</strong>
                    <div><i style={{ width: `${Math.max(3, (count / largestStatus) * 100)}%` }} /></div>
                  </div>
                ))}
            </div>
          </section>
          <section className="section-panel">
            <h3>Order value by currency</h3>
            <div className="demo-currency-list">
              {Object.entries(status.currency_value_totals).map(([currency, value]) => (
                <div key={currency}><span>{currency}</span><strong>{formatMoney(value, currency)}</strong></div>
              ))}
            </div>
            <div className="demo-guidance">
              <strong>Try it in ChatGPT</strong>
              <p>“Give me a management operations report for the last 30 days and identify the biggest bottleneck.”</p>
            </div>
          </section>
        </div>
      )}

      <section className="section-panel demo-safety">
        <h3>Built-in safeguards</h3>
        <ul>
          <li>Existing orders are never modified or removed.</li>
          <li>Synthetic email domains use the reserved <code>.example</code> suffix.</li>
          <li>Files use non-routable <code>demo://</code> references and cannot reach ERP or customers.</li>
          <li>Generation is repeat-safe, so clicking twice cannot create duplicate datasets.</li>
        </ul>
      </section>
    </div>
  );
}
