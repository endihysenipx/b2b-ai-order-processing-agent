export function UsersPage() {
  return (
    <section className="section-panel">
      <h2>Users</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Endi Hyseni</td>
            <td>admin@example.com</td>
            <td>Admin</td>
            <td>Active</td>
          </tr>
          <tr>
            <td>Imane Operator</td>
            <td>operator@example.com</td>
            <td>Operator</td>
            <td>Active</td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
