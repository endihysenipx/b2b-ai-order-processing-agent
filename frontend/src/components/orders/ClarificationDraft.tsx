import { useState } from "react";

import { apiRequest } from "../../api/client";

type Draft = { recipient: string; subject: string; body: string; questions: string[]; internal_notes: string[] };

export function ClarificationDraft({ orderId, revision, disabled }: { orderId: string; revision: string; disabled: boolean }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [sourceRevision, setSourceRevision] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const stale = Boolean(draft && sourceRevision !== revision);

  async function generate() {
    setBusy(true); setError(""); setCopied(false);
    try {
      const result = await apiRequest<Draft>(`/orders/${orderId}/clarification-draft`);
      setDraft(result); setSourceRevision(revision);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not prepare draft."); }
    finally { setBusy(false); }
  }

  async function copy() {
    if (!draft) return;
    setError("");
    try {
      await navigator.clipboard.writeText(`To: ${draft.recipient}\nSubject: ${draft.subject}\n\n${draft.body}`);
      setCopied(true);
    } catch { setError("Could not copy. Select the draft text and copy it manually."); }
  }

  function edit(field: "recipient" | "subject" | "body", value: string) {
    if (draft) setDraft({ ...draft, [field]: value });
    setCopied(false);
  }

  return <section className="section-panel clarification-panel">
    <h3>Customer clarification draft</h3>
    <p>Prepare questions from the saved order, review the recipient and wording, then copy into your email client.
      Nothing is sent. Draft edits stay on this page only.</p>
    <button disabled={disabled || busy} onClick={() => void generate()}>
      {busy ? "Preparing draft…" : draft ? "Regenerate draft (replaces edits)" : "Prepare clarification draft"}
    </button>
    {disabled && <p>Save or cancel order corrections before preparing or copying a draft.</p>}
    {error && <p role="alert" className="error-message">{error}</p>}
    {stale && <p role="status">The order changed. Regenerate the draft before copying it.</p>}
    {draft && <>
      {draft.internal_notes.length > 0 && <aside><h4>Internal review — not included in the message</h4>
        <ul>{draft.internal_notes.map(note => <li key={note}>{note}</li>)}</ul></aside>}
      {!draft.questions.length && <p>No customer clarification questions were found. Review any internal notes above.</p>}
      <label>Recipient<input type="email" value={draft.recipient} onChange={e => edit("recipient", e.target.value)} disabled={busy} /></label>
      <label>Subject<input value={draft.subject} onChange={e => edit("subject", e.target.value)} disabled={busy} /></label>
      <label>Message<textarea rows={12} value={draft.body} onChange={e => edit("body", e.target.value)} disabled={busy} /></label>
      <button disabled={busy || disabled || stale || !draft.body.trim()} onClick={() => void copy()}>{copied ? "Copied" : "Copy reviewed draft"}</button>
    </>}
  </section>;
}
