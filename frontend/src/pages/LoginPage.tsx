import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { apiRequest, getAccessToken, setAccessToken } from "../api/client";
import type { User } from "../types/user";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await apiRequest<{ access_token: string; user: User }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(result.access_token);
      const routeState = location.state as { from?: { pathname?: string; search?: string } } | null;
      const stateRedirect = routeState?.from?.pathname
        ? `${routeState.from.pathname}${routeState.from.search ?? ""}`
        : null;
      const target = stateRedirect ?? sessionStorage.getItem("post_login_redirect") ?? "/";
      sessionStorage.removeItem("post_login_redirect");
      navigate(target, { replace: true });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Login failed");
    }
  }

  if (getAccessToken()) {
    return <Navigate to="/" replace />;
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={handleSubmit}>
        <span className="eyebrow">FlowForge</span>
        <h1>Order Agent Login</h1>
        {error && <p className="error-message">{error}</p>}
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
        </label>
        <label>
          Password
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
        </label>
        <button type="submit">Log in</button>
      </form>
    </main>
  );
}
