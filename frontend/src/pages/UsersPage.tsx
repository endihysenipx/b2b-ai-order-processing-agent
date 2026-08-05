import { FormEvent, useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import type { Client } from "../types/client";
import type { User } from "../types/user";

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [selected, setSelected] = useState<User | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [createRole, setCreateRole] = useState("operator");
  const [temporaryPassword, setTemporaryPassword] = useState("");

  function load() {
    Promise.all([apiRequest<User[]>("/users"), apiRequest<Client[]>("/clients")])
      .then(([userData, clientData]) => {
        setUsers(userData);
        setClients(clientData);
        setSelected((current) => userData.find((user) => user.id === current?.id) ?? userData[0] ?? null);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load users"));
  }

  useEffect(load, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    const clientIds = form.getAll("client_ids").map(String);
    try {
      await apiRequest<User>(`/users/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          role: String(form.get("role")),
          is_active: form.get("is_active") === "on",
          client_ids: clientIds,
        }),
      });
      setMessage("Access updated.");
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update access");
    }
  }

  async function resetTwoFactor() {
    if (!selected || !window.confirm(`Reset two-factor authentication for ${selected.email}?`)) return;
    try {
      await apiRequest<void>(`/users/${selected.id}/2fa`, { method: "DELETE" });
      setMessage("Authenticator reset. The user must enroll again at next login.");
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reset authenticator");
    }
  }

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ user: User; temporary_password: string }>("/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: String(form.get("full_name")),
          email: String(form.get("email")),
          role: createRole,
          client_ids: form.getAll("new_client_ids").map(String),
        }),
      });
      setTemporaryPassword(result.temporary_password);
      setMessage(`User ${result.user.email} created. Share the temporary password securely.`);
      event.currentTarget.reset();
      setCreateRole("operator");
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create user");
    }
  }

  async function deleteUser(user: User) {
    if (!window.confirm(`Delete ${user.email}? This immediately revokes access but preserves historical audit records.`)) return;
    try {
      await apiRequest<void>(`/users/${user.id}`, { method: "DELETE" });
      setMessage("User deleted and access revoked.");
      if (selected?.id === user.id) setSelected(null);
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete user");
    }
  }

  return (
    <div className="page-stack">
      <form className="section-panel edit-form" onSubmit={createUser}>
        <h2>Create user</h2>
        <div className="order-form-grid">
          <label>Full name<input name="full_name" minLength={2} required /></label>
          <label>Email<input name="email" type="email" required /></label>
          <label>Role
            <select name="new_role" value={createRole} onChange={(event) => setCreateRole(event.target.value)}>
              <option value="operator">Operator</option><option value="admin">Administrator</option>
            </select>
          </label>
        </div>
        {createRole === "operator" && (
          <fieldset>
            <legend>Client access</legend>
            {clients.map((client) => (
              <label key={client.id}>
                <input type="checkbox" name="new_client_ids" value={client.id} />
                {client.client_name}
              </label>
            ))}
          </fieldset>
        )}
        <button type="submit">Create user</button>
        {temporaryPassword && (
          <div className="temporary-password">
            <strong>Temporary password — shown once</strong>
            <code>{temporaryPassword}</code>
            <p>Send it through a secure channel. The user must replace it before authenticator enrollment.</p>
            <button type="button" onClick={() => setTemporaryPassword("")}>I saved it</button>
          </div>
        )}
      </form>
      <div className="detail-grid">
        <section className="section-panel">
        <h2>Users</h2>
        {error && <p className="error-message">{error}</p>}
        {message && <p className="success-message">{message}</p>}
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>2FA</th><th>Actions</th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name}</td><td>{user.email}</td><td>{user.role}</td>
                <td>{user.totp_enabled ? "Enabled" : "Setup required"}</td>
                <td className="action-row">
                  <button type="button" onClick={() => setSelected(user)}>Manage</button>
                  <button type="button" className="danger-button" onClick={() => deleteUser(user)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <form className="section-panel edit-form" onSubmit={save} key={selected?.id}>
        <h2>Access</h2>
        {selected ? (
          <>
            <strong>{selected.email}</strong>
            <label>Role
              <select
                name="role"
                value={selected.role}
                onChange={(event) => setSelected({ ...selected, role: event.target.value })}
              >
                <option value="operator">Operator</option><option value="admin">Administrator</option>
              </select>
            </label>
            <label><input type="checkbox" name="is_active" defaultChecked={selected.is_active} /> Active</label>
            <fieldset disabled={selected.role === "admin"}>
              <legend>Client access</legend>
              {clients.map((client) => (
                <label key={client.id}>
                  <input type="checkbox" name="client_ids" value={client.id} defaultChecked={selected.client_ids.includes(client.id)} />
                  {client.client_name}
                </label>
              ))}
            </fieldset>
            <div className="action-row">
              <button type="submit">Save access</button>
              <button type="button" className="danger-button" onClick={resetTwoFactor}>Reset authenticator</button>
            </div>
          </>
        ) : <p>No users found.</p>}
        </form>
      </div>
    </div>
  );
}
