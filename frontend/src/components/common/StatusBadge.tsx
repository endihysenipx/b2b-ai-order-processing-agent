const statusClass: Record<string, string> = {
  OK: "status-ok",
  "Human in the Loop": "status-review",
  "Waiting for Reply": "status-waiting",
  Failed: "status-failed",
  "ERP Ready": "status-ready",
  "XMLs Sent": "status-sent",
  Approved: "status-approved",
  Rejected: "status-rejected",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge ${statusClass[status] ?? "status-default"}`}>{status}</span>;
}
