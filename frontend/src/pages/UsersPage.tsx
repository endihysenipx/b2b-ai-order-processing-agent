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

  return (
    <div className="detail-grid">
      <section className="section-panel">
        <h2>Users</h2>
        {error && <p className="error-message">{error}</p>}
        {message && <p className="success-message">{message}</p>}
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>2FA</th><th>Open</th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name}</td><td>{user.email}</td><td>{user.role}</td>
                <td>{user.totp_enabled ? "Enabled" : "Setup required"}</td>
                <td><button type="button" onClick={() => setSelected(user)}>Manage</button></td>
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
  );
}
