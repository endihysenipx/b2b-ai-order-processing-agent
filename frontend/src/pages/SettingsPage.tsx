export function SettingsPage() {
  return (
    <section className="section-panel settings-grid">
      <h2>Settings</h2>
      <div>
        <h3>Inbox</h3>
        <p>Microsoft Graph configuration placeholders are managed through environment variables.</p>
      </div>
      <div>
        <h3>AI Extraction</h3>
        <p>AI extraction uses the provider selected by AI_PROVIDER. Amazon Bedrock and local mock modes are supported.</p>
      </div>
      <div>
        <h3>XML and ERP</h3>
        <p>XML generation writes local files. ERP sending is simulated during Week 3.</p>
      </div>
    </section>
  );
}
