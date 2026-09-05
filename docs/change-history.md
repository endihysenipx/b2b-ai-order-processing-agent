# Change history

The **Change History** page records committed user changes made through the
application. It shows who acted, when, which customer/record was affected, and the
before/after values of changed fields. Filter by customer, record type, actor name,
or UTC date range. Results are paginated, newest first. Orders and customer/product
data link to their related history; import entries link to the full import batch.

## Coverage

- Manual customer contact, address, active-status and validation-setting changes.
- Product creation and edits, including agreed price, currency, stock, reservations,
  warehouse, observation time, aliases, minimum quantity and active status.
- Confirmed catalog imports: one entry per changed product, sharing a batch ID.
- Order header and line corrections, including prices and quantities.
- Approvals, rejections, validation-driven status changes, approval clearing after
  corrections/revalidation, and XML-related status transitions.

Only changed fields are retained. Equivalent prices are normalized to two decimal
places, timestamps to UTC, and unchanged saves do not add entries. Import previews
and rejected validation requests that change nothing do not add history. An action
blocked by validation can clear an existing approval and change order status; those
committed changes are recorded as `validation_blocked_action`.

## Storage and access

Run `alembic upgrade head` before starting the updated backend. Revision
`202609050009` adds the `audit_events` table and indexes without altering existing
customer/order records. The existing deployment path runs migrations automatically.
There is no retrospective history: old changes cannot be attributed reliably, and
no user, time or before-value is fabricated.

Audit entries are inserted in the same transaction as the mutation. A rollback
removes both the data changes and their audit entries. Catalog writes use the
existing per-customer lock; order mutations now lock the order before reading the
before-values. Actor ID and display name are captured from the authenticated user,
not accepted from request payloads. Record identifiers and display names are
snapshots, so removing a source record or renaming an account does not erase or
rewrite historical attribution.

History uses the existing client access rules: admins/managers can read across
customers, and operators can read only currently assigned customers. Scope is
applied before both counting and paging, including record/batch-specific queries.
There are no edit/delete history endpoints; ORM updates/deletes are rejected.
This is application-level history, not a tamper-proof external ledger: privileged
database access can bypass ORM protection. Retention/backups should follow the same
protected-data practices as the customer database. Downgrading this migration drops
the history table; preserve a backup first if history must be retained.

Only explicitly allowed business fields are captured. Passwords, access tokens,
MFA secrets, extraction prompts, uploaded files and raw email bodies are excluded.
Customer contact/address changes do contain business/customer information, and are
therefore subject to the same authorization as the underlying records. Direct SQL,
seed scripts and initial automated extraction are not retrospectively attributed to
a user; future mutation paths must call the shared audit service in their transaction.

## API

`GET /api/v1/history` accepts `client_id`, `entity_type` (`customer`, `product`,
`order`, `order_item`), `entity_id`, `order_id`, `actor` (name search), `actor_id`,
`batch_id`, `date_from`, `date_to`, `page` and `page_size` (maximum 100). It returns
`items`, `total`, `page`, and `page_size`. Each entry has a `changes` object whose
field keys map to `{before, after}` values.
