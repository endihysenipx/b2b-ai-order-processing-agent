# Order corrections

Open an order to edit its header or any existing line. Each line has independent
Save and Cancel buttons. Failed requests preserve the draft and show the error.
Saving one line leaves drafts on other lines intact. Save or cancel all drafts
before using Validate, Approve, Reject or XML actions. Browser refresh/close warns
about unsaved drafts; save before navigating to another page within the application.

Search the selected customer's catalog by SKU, description or customer article
alias. Choose a product to copy its canonical SKU into the article draft. Choosing
a match does not change the price automatically: use **Use agreed price** to apply
the catalog price and currency. The match displays account-specific availability,
warehouse, minimum quantity, unit and stock observation time. Stale snapshots are
marked. Catalog-loading failures leave manual correction available.

Editable line fields: article, model, quantity, unit price, currency and source
total. When quantity and unit price are both present, the line total is calculated
using exact cents in the browser and Decimal arithmetic on the server. Otherwise,
a source total can be entered explicitly. Clearing quantity or unit price clears
the old calculated total unless a source total was explicitly supplied. The header
total is a separate source field and is not automatically replaced with a sum of
lines (it may include charges not represented by the extracted lines).

Quantity must be a positive integer or empty. Amounts must be nonnegative, have
at most two decimal places and fit the existing database precision. Currency is
an uppercase three-letter code or empty. Empty required data is retained as a
validation issue requiring review; no values are invented.

Saving reruns validation, clears approval and generated XML metadata, and updates
the status. Unresolved validation messages appear beside the relevant header or
line fields, with a summary and links to the affected lines. Stock shortages are
summed across matching SKUs/aliases and attached to each affected quantity field.
Resolved issues are hidden from the open-issues display. Messages describe saved
data and refresh after Save or Validate; unsaved drafts have not been validated.

The existing authenticated, client-scoped PATCH endpoints are used. A line cannot
be edited through another order. No new stock mutations, deletion actions, database
migrations, or automatic approval behavior are introduced.
