import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiRequest, setAccessToken } from "../api/client";
import type { User } from "../types/user";

export function LoginPage() {
  const navigate = useNavigate();
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
      navigate("/");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Login failed");
    }
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
