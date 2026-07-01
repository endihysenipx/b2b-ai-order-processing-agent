import { FormEvent, useEffect, useState } from "react";

import { apiRequest } from "../api/client";

interface FeedbackIssue {
  id: string;
  category: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
}

export function FeedbackIssuesPage() {
  const [issues, setIssues] = useState<FeedbackIssue[]>([]);

  function loadIssues() {
    apiRequest<FeedbackIssue[]>("/feedback").then(setIssues);
  }

  useEffect(loadIssues, []);

  async function createIssue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    await apiRequest("/feedback", {
      method: "POST",
      body: JSON.stringify({
        category: formData.get("category"),
        title: formData.get("title"),
        description: formData.get("description"),
      }),
    });
    event.currentTarget.reset();
    loadIssues();
  }

  return (
    <div className="detail-grid">
      <section className="section-panel">
        <h2>Feedback & Issues</h2>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Title</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {issues.map((issue) => (
              <tr key={issue.id}>
                <td>{issue.category}</td>
                <td>{issue.title}</td>
                <td>{issue.status}</td>
                <td>{new Date(issue.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <form className="section-panel edit-form" onSubmit={createIssue}>
        <h2>Create Issue</h2>
        <label>
          Category
          <input name="category" defaultValue="extraction" />
        </label>
        <label>
          Title
          <input name="title" required />
        </label>
        <label>
          Description
          <textarea name="description" required />
        </label>
        <button type="submit">Create issue</button>
      </form>
    </div>
  );
}
