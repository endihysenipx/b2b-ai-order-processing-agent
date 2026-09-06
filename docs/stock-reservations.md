# Stock reservations

For real orders with customer master-data validation enabled, approval allocates catalog stock. XML generation and sending also establish missing allocations for legacy unsent orders. SKU and alias lines are summed by product; repeated approvals are idempotent. Available quantity is on-hand minus external reserved quantity minus this application's order reservations. Validation credits the current order's own allocation.

All order mutations acquire the customer's database row lock before the order lock. Catalog saves and confirmed imports share that customer lock. Under production PostgreSQL this serializes competing approvals and stock updates through validation, allocation and commit. Reservation rows and audit events are in the same transaction. SQLite local tests cover lifecycle behavior, not PostgreSQL row-lock contention.

Header/item correction, rejection, explicit validation and failed validation gates release unsent allocations. Approval reserves again. Sent orders retain allocations and cannot be edited, rejected, revalidated or exported again through these endpoints. A fulfillment/ERP reconciliation workflow is needed to consume or release sent allocations; this change does not decrement on-hand stock.

The existing reserved input means reservations outside this app. Imports cannot overwrite app allocations. A new physical-stock snapshot can reveal negative availability; existing allocations remain visible and further processing is blocked by validation. Do not include app allocations in the external reserved input or they will be counted twice.

Demo orders and customers with master-data validation disabled do not create new allocations. Catalog quantities are customer-specific, not a shared warehouse pool across customers. Existing allocations survive disabling validation until the order is corrected or rejected. Previously approved/sent orders are not automatically backfilled; reconcile historical commitments before relying on the new available quantity.

Migration 202609060011 adds stock_reservations with positive quantities, foreign keys and one row per order/product. Downgrading deletes the reservation ledger. Reservation changes appear in Change History as stock_reserved and stock_released with the associated order ID. No stock snapshot timestamp is changed by reservation actions.
