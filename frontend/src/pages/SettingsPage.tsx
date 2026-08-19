import { FormEvent, useState } from "react";

import { apiRequest, clearAccessToken } from "../api/client";

export function SettingsPage() {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function resetAuthenticator(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm("Replace your authenticator and sign out of every active session?")) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest<void>("/auth/2fa/reset", {
        method: "POST",
        body: JSON.stringify({ password, code }),
      });
      clearAccessToken();
      window.location.assign("/login?mfa_reset=1");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reset the authenticator");
      setBusy(false);
    }
  }

  return (
    <section className="section-panel settings-grid">
      <h2>Settings</h2>
      <div className="security-settings">
        <h3>Authenticator</h3>
        <p>
          Replace the authenticator linked to your account. This signs you out everywhere; your next login will show a
          new QR code to scan on the new phone.
        </p>
        <p><strong>Use a fresh code.</strong> If you just logged in, wait for the next six-digit code, or use a recovery code.</p>
        <form onSubmit={resetAuthenticator}>
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <label>
            Current authenticator or recovery code
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              minLength={6}
              maxLength={32}
              required
            />
          </label>
          {error && <p className="error-message">{error}</p>}
          <button type="submit" className="danger-button" disabled={busy}>
            {busy ? "Resetting…" : "Reset and enroll a new authenticator"}
          </button>
        </form>
      </div>
      <div>
        <h3>Inbox</h3>
        <p>Microsoft Graph configuration placeholders are managed through environment variables.</p>
      </div>
      <div>
        <h3>AI Extraction</h3>
        <p>AI extraction uses the provider selected by AI_PROVIDER. Amazon Bedrock and local mock modes are supported.</p>
      </div>
      <div>
        <h3>XML and ERP</h3>
        <p>XML generation writes local files. ERP sending is simulated during Week 3.</p>
      </div>
    </section>
  );
}
