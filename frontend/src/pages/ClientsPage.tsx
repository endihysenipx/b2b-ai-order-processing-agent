import { useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import type { Client } from "../types/client";

export function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [selected, setSelected] = useState<Client | null>(null);

  useEffect(() => {
    apiRequest<Client[]>("/clients").then((data) => {
      setClients(data);
      setSelected(data[0] ?? null);
    });
  }, []);

  return (
    <div className="detail-grid">
      <section className="section-panel">
        <h2>Clients</h2>
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>Customer No.</th>
              <th>Email Domain</th>
              <th>Status</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.id}>
                <td>{client.client_name}</td>
                <td>{client.customer_number}</td>
                <td>{client.email_domain}</td>
                <td>{client.is_active ? "Active" : "Inactive"}</td>
                <td>
                  <button onClick={() => setSelected(client)}>Open</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="section-panel">
        <h2>Client Details</h2>
        {selected ? (
          <>
            <h3>{selected.client_name}</h3>
            <p>{selected.extraction_prompt}</p>
            <h4>Required Fields</h4>
            <ul>
              {selected.required_fields.map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
            <h4>Validation Rules</h4>
            <pre>{JSON.stringify(selected.validation_rules, null, 2)}</pre>
          </>
        ) : (
          <p className="empty-state">No client selected.</p>
        )}
      </section>
    </div>
  );
}
