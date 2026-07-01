export function DataExportPage() {
  return (
    <section className="section-panel export-panel">
      <h2>Data Export</h2>
      <div className="toolbar">
        <label>
          From
          <input type="date" />
        </label>
        <label>
          To
          <input type="date" />
        </label>
        <label>
          Client
          <select>
            <option>All clients</option>
          </select>
        </label>
        <label>
          Status
          <select>
            <option>All statuses</option>
          </select>
        </label>
        <button disabled>Export to Excel</button>
      </div>
      <p className="empty-state">Excel export is planned for a later sprint; the Week 3 UI structure is ready.</p>
    </section>
  );
}
