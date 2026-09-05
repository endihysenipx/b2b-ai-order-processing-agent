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
