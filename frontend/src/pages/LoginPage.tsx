import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { apiRequest, getAccessToken, setAccessToken, setAuthenticatedUser } from "../api/client";
import type { User } from "../types/user";

interface LoginResult {
  access_token: string | null;
  user: User | null;
  challenge_token: string | null;
  requires_2fa: boolean;
  requires_2fa_setup: boolean;
  requires_password_change: boolean;
  recovery_codes?: string[] | null;
}

interface SetupResult {
  secret: string;
  provisioning_uri: string;
  qr_code_data_url: string;
}

type Stage = "credentials" | "password" | "setup" | "verify" | "recovery";

function resolvePostLoginTarget(location: ReturnType<typeof useLocation>) {
  const routeState = location.state as { from?: { pathname?: string; search?: string } } | null;
  const stateRedirect = routeState?.from?.pathname
    ? `${routeState.from.pathname}${routeState.from.search ?? ""}`
    : null;
  const queryRedirect = new URLSearchParams(location.search).get("next");
  const safeQueryRedirect = queryRedirect?.startsWith("/oauth/authorize?request=")
    ? queryRedirect
    : null;
  return stateRedirect ?? safeQueryRedirect ?? sessionStorage.getItem("post_login_redirect") ?? "/";
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const postLoginTarget = resolvePostLoginTarget(location);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [challengeToken, setChallengeToken] = useState("");
  const [setup, setSetup] = useState<SetupResult | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [stage, setStage] = useState<Stage>("credentials");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function finishLogin(result: LoginResult) {
    if (!result.access_token || !result.user) {
      throw new Error("The server did not return a completed session");
    }
    setAccessToken(result.access_token);
    setAuthenticatedUser(result.user);
    if (result.recovery_codes?.length) {
      setRecoveryCodes(result.recovery_codes);
      setStage("recovery");
      return;
    }
    navigateAfterLogin();
  }

  function navigateAfterLogin() {
    sessionStorage.removeItem("post_login_redirect");
    navigate(postLoginTarget, { replace: true });
  }

  async function submitCredentials(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await apiRequest<LoginResult>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (!result.challenge_token) {
        finishLogin(result);
      } else if (result.requires_password_change) {
        setChallengeToken(result.challenge_token);
        setStage("password");
      } else if (result.requires_2fa_setup) {
        setChallengeToken(result.challenge_token);
        const setupResult = await apiRequest<SetupResult>("/auth/2fa/setup", {
          method: "POST",
          body: JSON.stringify({ challenge_token: result.challenge_token }),
        });
        setSetup(setupResult);
        setStage("setup");
      } else {
        setChallengeToken(result.challenge_token);
        setStage("verify");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitNewPassword(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const changed = await apiRequest<LoginResult>("/auth/password/change", {
        method: "POST",
        body: JSON.stringify({ challenge_token: challengeToken, new_password: newPassword }),
      });
      if (!changed.challenge_token || !changed.requires_2fa_setup) {
        throw new Error("The server did not start authenticator enrollment");
      }
      setChallengeToken(changed.challenge_token);
      const setupResult = await apiRequest<SetupResult>("/auth/2fa/setup", {
        method: "POST",
        body: JSON.stringify({ challenge_token: changed.challenge_token }),
      });
      setSetup(setupResult);
      setCode("");
      setStage("setup");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const endpoint = stage === "setup" ? "/auth/2fa/enable" : "/auth/2fa/verify";
      const result = await apiRequest<LoginResult>(endpoint, {
        method: "POST",
        body: JSON.stringify({ challenge_token: challengeToken, code }),
      });
      finishLogin(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  if (getAccessToken() && stage !== "recovery") {
    return <Navigate to={postLoginTarget} replace />;
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <span className="eyebrow">FlowForge</span>
        <h1>Order Agent Login</h1>
        {error && <p className="error-message">{error}</p>}

        {stage === "credentials" && (
          <form onSubmit={submitCredentials}>
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" required />
            </label>
            <label>
              Password
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required />
            </label>
            <button type="submit" disabled={busy}>{busy ? "Checking…" : "Continue"}</button>
          </form>
        )}

        {stage === "setup" && setup && (
          <form onSubmit={submitCode}>
            <h2>Set up your authenticator</h2>
            <p>Scan this QR code with Google Authenticator, Microsoft Authenticator, 1Password, or another TOTP app.</p>
            <img className="totp-qr" src={setup.qr_code_data_url} alt="Authenticator setup QR code" />
            <details>
              <summary>Cannot scan the QR code?</summary>
              <p>Enter this setup key manually:</p>
              <code className="setup-secret">{setup.secret}</code>
            </details>
            <label>
              Six-digit code
              <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required />
            </label>
            <button type="submit" disabled={busy}>{busy ? "Verifying…" : "Enable authenticator"}</button>
          </form>
        )}

        {stage === "password" && (
          <form onSubmit={submitNewPassword}>
            <h2>Choose a new password</h2>
            <p>Your administrator gave you a temporary password. Replace it before setting up your authenticator.</p>
            <label>
              New password
              <input
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                autoFocus
              />
            </label>
            <label>
              Confirm new password
              <input
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            <small>Use at least 12 characters with uppercase, lowercase, a number, and a symbol.</small>
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Set password and continue"}</button>
          </form>
        )}

        {stage === "verify" && (
          <form onSubmit={submitCode}>
            <h2>Two-factor authentication</h2>
            <p>Enter the six-digit code from your authenticator app. You may also enter one unused recovery code.</p>
            <label>
              Authenticator or recovery code
              <input value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required autoFocus />
            </label>
            <button type="submit" disabled={busy}>{busy ? "Verifying…" : "Log in"}</button>
          </form>
        )}

        {stage === "recovery" && (
          <div>
            <h2>Save your recovery codes</h2>
            <p>Store these somewhere secure. Each code works once and they will not be shown again.</p>
            <pre className="recovery-codes">{recoveryCodes.join("\n")}</pre>
            <button type="button" onClick={navigateAfterLogin}>I saved these codes</button>
          </div>
        )}
      </section>
    </main>
  );
}
