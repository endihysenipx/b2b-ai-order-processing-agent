import { DragEvent, FormEvent, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clipboard,
  Clock3,
  Mail,
  ScanSearch,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/common/StatusBadge";
import type { IntelligenceStepStatus, OrderIntelligenceResult } from "../types/intelligence";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const DEMO_EMAIL = `Message-ID: <flowforge-order-intelligence-exception-demo-v1@demo.invalid>
From: orders@lutz-demo.invalid
To: order-processing@flowforge.invalid
Subject: Bestellung DEMO26 von Lutz
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8

Filiale: Mentor Demo Store, Budapest
Liefertermin: KW38/2026
MENTOR EXCEPTION DEMO
Komm: DEMO26-1
2 x MODEL26-ART2601 (1) Demonstration cabinet
Details zur Bestellung:
`;

function displayLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function TimelineIcon({ status }: { status: IntelligenceStepStatus }) {
  if (status === "completed") return <CheckCircle2 aria-hidden="true" />;
  if (status === "queued") return <Clock3 aria-hidden="true" />;
  return <AlertTriangle aria-hidden="true" />;
}

export function OrderIntelligencePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<OrderIntelligenceResult | null>(null);
  const [copied, setCopied] = useState(false);

  function selectFile(candidate: File | null) {
    setError("");
    setResult(null);
    if (!candidate) {
      setFile(null);
      return;
    }
    if (!candidate.name.toLowerCase().endsWith(".eml")) {
      setFile(null);
      setError("Choose an RFC 822 email file ending in .eml.");
      return;
    }
    if (candidate.size > MAX_FILE_BYTES) {
      setFile(null);
      setError("The email exceeds the 10 MB upload limit.");
      return;
    }
    setFile(candidate);
  }

  function loadDemo() {
    selectFile(new File([DEMO_EMAIL], "flowforge-exception-demo.eml", { type: "message/rfc822" }));
  }

  function dropFile(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    selectFile(event.dataTransfer.files[0] ?? null);
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      const body = new FormData();
      body.append("file", file);
      const imported = await apiRequest<OrderIntelligenceResult>("/emails/intelligence/import", {
        method: "POST",
        body,
      });
      setResult(imported);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The email could not be processed");
    } finally {
      setBusy(false);
    }
  }

  async function copyDraft() {
    if (!result?.clarification_draft) return;
    await navigator.clipboard.writeText(result.clarification_draft);
    setCopied(true);
  }

  return (
    <div className="page-stack intelligence-page">
      <section className="intelligence-hero">
        <div>
          <span className="eyebrow">Explainable automation</span>
          <h2>Order Intelligence</h2>
          <p>
            Turn a raw customer email into a validated order record with visible evidence, duplicate protection, and a
            human decision before approval or ERP preparation.
          </p>
        </div>
        <div className="intelligence-safety">
          <ShieldCheck aria-hidden="true" />
          <div>
            <strong>Human approval enforced</strong>
            <span>No email is sent and no order is approved automatically.</span>
          </div>
        </div>
      </section>

      <section className="section-panel intelligence-upload-panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Start a workflow</span>
            <h3>Upload a purchase-order email</h3>
          </div>
          <button type="button" className="tab" onClick={loadDemo}>Load exception demo</button>
        </div>
        <form onSubmit={analyze}>
          <div
            className={`intelligence-drop-zone ${dragActive ? "drag-active" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={dropFile}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
            }}
            role="button"
            tabIndex={0}
          >
            <UploadCloud size={34} aria-hidden="true" />
            <strong>{file ? file.name : "Drop an .eml file here"}</strong>
            <span>{file ? `${Math.max(1, Math.round(file.size / 1024))} KB selected` : "or click to choose an email, up to 10 MB"}</span>
            <input
              ref={inputRef}
              className="file-input"
              type="file"
              accept=".eml,message/rfc822"
              onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
              tabIndex={-1}
            />
          </div>
          {error && <p className="error-message">{error}</p>}
          <div className="intelligence-upload-actions">
            <small>Re-uploading the same Message-ID returns the existing order instead of creating a duplicate.</small>
            <button type="submit" disabled={!file || busy}>
              <ScanSearch size={18} aria-hidden="true" />
              {busy ? "Processing evidence…" : "Analyze and import"}
            </button>
          </div>
        </form>
      </section>

      {!result && !busy && (
        <section className="intelligence-capabilities" aria-label="Order Intelligence capabilities">
          <article>
            <Mail aria-hidden="true" />
            <strong>Classify</strong>
            <span>Detect the message type and customer profile.</span>
          </article>
          <article>
            <ScanSearch aria-hidden="true" />
            <strong>Extract</strong>
            <span>Map order headers, line items, references, and attachments.</span>
          </article>
          <article>
            <ShieldCheck aria-hidden="true" />
            <strong>Validate</strong>
            <span>Apply business rules and route uncertainty to a person.</span>
          </article>
        </section>
      )}

      {busy && <p className="loading">Running classification, evidence extraction, duplicate checks, and validation…</p>}

      {result && (
        <>
          {result.duplicate && (
            <p className="intelligence-notice"><ShieldCheck size={18} aria-hidden="true" />This message was already imported. FlowForge reused the existing records.</p>
          )}

          <section className="kpi-grid intelligence-kpis">
            <article className="kpi-card">
              <span>Classification</span>
              <strong>{displayLabel(result.classification)}</strong>
              <small>{result.subject}</small>
            </article>
            <article className="kpi-card">
              <span>Detected client</span>
              <strong>{result.client_name ?? "Unmatched"}</strong>
              <small>{Math.round(result.client_confidence * 100)}% profile confidence</small>
            </article>
            <article className="kpi-card">
              <span>Orders created</span>
              <strong>{result.orders.length}</strong>
              <small>{result.orders.reduce((total, order) => total + order.item_count, 0)} line items extracted</small>
            </article>
            <article className={`kpi-card decision-card ${result.requires_review ? "needs-review" : "ready"}`}>
              <span>Decision</span>
              <strong>{result.requires_review ? "Human review" : "Ready"}</strong>
              <small>{displayLabel(result.next_action)}</small>
            </article>
          </section>

          <section className="section-panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Processing trace</span>
                <h3>Explainable workflow timeline</h3>
              </div>
              <span className="mode-pill">{result.requires_review ? "Human review required" : "Ready for approval"}</span>
            </div>
            <ol className="intelligence-timeline">
              {result.timeline.map((step) => (
                <li key={step.key} className={`timeline-${step.status}`}>
                  <span className="timeline-icon"><TimelineIcon status={step.status} /></span>
                  <div>
                    <strong>{step.label}</strong>
                    <p>{step.detail}</p>
                  </div>
                  <small>{step.status === "attention" ? "Needs attention" : displayLabel(step.status)}</small>
                </li>
              ))}
            </ol>
          </section>

          <section className="detail-grid intelligence-details">
            <div className="section-panel">
              <span className="eyebrow">Source evidence</span>
              <h3>Why FlowForge made this decision</h3>
              <dl className="metadata-list">
                <dt>Sender</dt>
                <dd>{result.sender_email}</dd>
                <dt>Subject</dt>
                <dd>{result.subject}</dd>
                <dt>References</dt>
                <dd>{result.reference_codes.join(", ") || "None detected"}</dd>
                <dt>Profile</dt>
                <dd>{result.client_profile ? displayLabel(result.client_profile) : "Manual assignment needed"}</dd>
              </dl>
              {result.client_evidence.length > 0 && (
                <div className="evidence-block">
                  <strong>Detection signals</strong>
                  <ul>{result.client_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>
              )}
              {result.attachments.length > 0 && (
                <div className="evidence-block">
                  <strong>Attachments</strong>
                  <ul>
                    {result.attachments.map((attachment) => (
                      <li key={attachment.file_name}>
                        {attachment.file_name} — {attachment.is_scanned ? "scanned evidence" : displayLabel(attachment.processing_status)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {result.notes.length > 0 && (
                <div className="evidence-block">
                  <strong>Pipeline notes</strong>
                  <ul>{result.notes.map((note) => <li key={note}>{note}</li>)}</ul>
                </div>
              )}
            </div>

            <div className="section-panel">
              <span className="eyebrow">Human handoff</span>
              <h3>Created orders</h3>
              {result.orders.length === 0 ? (
                <p className="empty-state">No order was created. Assign the message for manual review.</p>
              ) : (
                <div className="intelligence-order-list">
                  {result.orders.map((order) => (
                    <article key={order.id}>
                      <div>
                        <strong>{order.ticket_number ?? order.commission_number ?? order.id.slice(0, 8)}</strong>
                        <span>{order.commission_number} · {order.delivery_week ?? "Delivery week missing"}</span>
                      </div>
                      <StatusBadge status={order.status} />
                      <p>{order.item_count} item(s) · {order.issue_count} open issue(s)</p>
                      <Link to={`/orders/${order.id}`}>Review order <ArrowRight size={16} aria-hidden="true" /></Link>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>

          {result.clarification_draft && (
            <section className="section-panel clarification-panel">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">Suggested response</span>
                  <h3>Clarification draft</h3>
                </div>
                <button type="button" className="tab" onClick={copyDraft}>
                  <Clipboard size={17} aria-hidden="true" /> {copied ? "Copied" : "Copy draft"}
                </button>
              </div>
              <textarea value={result.clarification_draft} readOnly aria-label="Clarification draft" />
              <small>This is a review draft only. FlowForge has not sent an email.</small>
            </section>
          )}
        </>
      )}
    </div>
  );
}
