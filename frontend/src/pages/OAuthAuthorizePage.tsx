import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { apiRequest, getAccessToken, getAuthenticatedUser } from "../api/client";
import type { User } from "../types/user";

interface AuthorizationRedirect {
  redirect_url: string;
}

export function OAuthAuthorizePage() {
  const location = useLocation();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestToken = new URLSearchParams(location.search).get("request");
  const user = getAuthenticatedUser<User>();

  if (!requestToken) {
    return (
      <main className="login-page">
        <section className="login-panel">
          <h1>Invalid authorization request</h1>
          <p className="error-message">The ChatGPT authorization request is missing.</p>
        </section>
      </main>
    );
  }

  if (!getAccessToken()) {
    sessionStorage.setItem("post_login_redirect", `${location.pathname}${location.search}`);
    return <Navigate to="/login" replace />;
  }

  async function decide(approved: boolean) {
    setError("");
    setBusy(true);
    try {
      const result = await apiRequest<AuthorizationRedirect>("/oauth/authorize/complete", {
        method: "POST",
        body: JSON.stringify({ request_token: requestToken, approved }),
      });
      window.location.assign(result.redirect_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authorization could not be completed");
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel oauth-consent-panel">
        <span className="eyebrow">FlowForge</span>
        <h1>Connect ChatGPT</h1>
        <p>
          ChatGPT is requesting read-only access to the B2B order tools as <strong>{user?.email ?? "your account"}</strong>.
        </p>
        <ul>
          <li>Search and inspect orders you are already allowed to see</li>
          <li>Read daily briefings, attention queues, evidence, and reports</li>
          <li>No approvals, email sending, ERP transmission, deletion, or reprocessing</li>
        </ul>
        <p>You can disconnect the plugin from ChatGPT at any time.</p>
        {error && <p className="error-message">{error}</p>}
        <div className="consent-actions">
          <button type="button" className="secondary" disabled={busy} onClick={() => decide(false)}>Cancel</button>
          <button type="button" disabled={busy} onClick={() => decide(true)}>{busy ? "Connecting…" : "Allow read-only access"}</button>
        </div>
      </section>
    </main>
  );
}
