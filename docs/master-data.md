# Customer and product data

The Customer & Product Data page lets administrators maintain customer contacts,
approved delivery addresses, a customer catalog, article aliases, agreed prices,
minimum quantities, and stock snapshots. Other users can read only the clients
allowed by their existing account permissions. All writes require an administrator
and record actor and record identifiers in application logs.

Run `alembic upgrade head` from `backend` before starting the updated application.
The migration preserves existing customers and defaults their master-data checks
to disabled. Populate a customer's approved addresses and catalog, then enable
checks on their customer form. No real customer data is included in this change.

Products are scoped to a customer. SKU and aliases are unique within that customer's
catalog. Each entry currently holds one warehouse snapshot of availability allocated
to that customer, plus an optional agreed price and currency. This is not a shared
warehouse inventory ledger: do not copy the same shared stock into multiple customer
allocations. A future ERP integration should supply authoritative allocations.

Stock observations require an explicit timestamp with timezone. Available quantity
is on-hand minus reserved. Snapshots older than 24 hours, missing stock, inactive
products, unrecognized articles, address mismatches, shortages, and pricing or
minimum-quantity mismatches require review. Repeated lines and aliases are summed
for shortage checks. No stock is reserved or decremented by this application.

Validation is used by email intake, AI intake, REST validation and MCP's existing
read-only validation tool. For enabled clients, approval and XML actions rerun checks
and reject unresolved errors. Editing orders clears approval and generated XML
metadata so that old exports cannot be sent after an edit. The explicit Validate
action persists current findings and recomputes status. Missing required information
routes to Waiting for Reply; other errors and warnings route to Human in the Loop.

REST endpoints (under `/api/v1`):

- `PUT /clients/{id}/customer-data`: replace contact/address/check settings.
- `GET /clients/{id}/products`: read the customer catalog.
- `POST /clients/{id}/products`: create an entry.
- `PUT /clients/{id}/products/{product_id}`: replace an entry, including its snapshot.

Disable entries instead of deleting them. ERP synchronization, multiple warehouses
per product, shared inventory reservations and automatic refresh are not implemented.
Production deployment continues through the existing GitHub Actions workflow.

## Import a catalog

On Customer & Product Data, select the customer and use **Import product catalog**.
Only administrators can download the template, preview files, or confirm imports.

1. Download the blank CSV template. Fill it with your actual catalog, or create a
   single-sheet `.xlsx` workbook with the same headers.
2. Upload the file and select **Preview import**. Each row shows its file row number,
   SKU, planned action, errors, warnings, and current/proposed field values.
3. Resolve errors in the source file and upload it again. Any error blocks the entire
   batch; valid rows are not silently imported from an invalid batch.
4. Review the values, check the confirmation box and select **Confirm import**.
   The catalog refreshes after the transaction succeeds.

Limits: 2 MB uploaded, 500 data rows, one worksheet, 10 MB expanded Excel contents.
CSV files must be comma-separated UTF-8 (a BOM is accepted). Excel formulas and error
cells are rejected; paste their values first. Keep SKUs and aliases as text in Excel
to preserve leading zeros. Old `.xls` and macro-enabled workbooks are not supported.

Supported headers: `sku`, `description`, `unit`, `is_active`, `aliases`, `unit_price`,
`currency`, `minimum_quantity`, `warehouse`, `on_hand`, `reserved`, `stock_updated_at`.
Headers are case-insensitive, with spaces accepted in place of underscores.
`article_number` maps to `sku`; `product_name` and `product_description` map to
`description`. Unrecognized or duplicate headers are rejected rather than ignored.

SKU identifies an existing product within the selected customer. New SKUs create
products and require a description. Missing or blank cells preserve existing values;
new products use the existing form defaults. Nonblank aliases replace the alias list
and use `|` as the separator. Use the product edit form to clear existing values.
Use decimal points for prices, `true`/`false` for active status, and an ISO timestamp
with timezone for stock observations. Stock and price fields obey the same validation
as manual editing. Unknown or old stock is shown as a preview warning.

Duplicate SKUs within the file and conflicting SKUs/aliases in the resulting catalog
block the import. No products are deleted. Customer settings, order approvals and
stock reservations are not changed by an import.

The preview stores nothing in the database. A signed 15-minute token binds the file,
customer, administrator and catalog snapshot. Confirmation uploads the same file and
revalidates it while holding the same customer lock as manual catalog writes. A
changed file/catalog, expired token, or validation failure requires another preview.
All writes commit together; database conflicts roll the entire batch back. Logs contain
actor/client IDs and counts, without the uploaded rows. Files are not retained by the
import service.

API paths under `/api/v1/clients/{id}/catalog-import`:

- `GET /template`: blank CSV download.
- `POST /preview`: multipart `file`; returns rows, counts and a confirmation token
  only when all rows are valid.
- `POST /confirm`: multipart `file`, `token`, `confirmed=true`; returns created,
  updated and unchanged counts.
