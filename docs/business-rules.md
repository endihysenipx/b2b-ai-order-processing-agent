# Client business rules

The dashboard's Business Rules page supports freight below a merchandise threshold,
percentage discounts at or above a threshold, a minimum merchandise order, and
approval requirements for high final totals. Administrators can edit the rules;
other users can inspect only their permitted clients and cases.

All amounts use decimal arithmetic, with half-up rounding to two places. Merchandise
subtotal comes from the lines (quantity × unit price, or a supplied line total).
An order header total is used only when no lines exist. Freight and discount
thresholds use the subtotal before adjustments; review uses subtotal − discount +
freight. There is no currency conversion or tax calculation. Missing prices and
inconsistent currencies block approval when commercial rules are enabled.

Saving rules recalculates unsent, non-rejected orders and invalidates their
approvals and generated XML. Sent orders retain snapshots of their agreed rules.
Minimum-order failures block approval and XML export. Review thresholds require
explicit order approval before XML export. XML headers include CommercialTerms
with MerchandiseSubtotal, Discount, Freight, Currency, and TotalPayable.

Cases are explicit edits of source records, not duplicate imports. The conversion
reassigns the source email and its single order (or creates an order if parsing
failed), sets the client's identity, and replaces the line items with the entered
example. It labels the order as demo data, preserves the original attachments,
records the original editable data in change history, and prevents background OCR
from rewriting the case. Conversion rejects sent orders, sources with multiple
orders, sources still processing, and already-converted cases. Later edits use
the existing order detail page and automatically recalculate commercial terms.
