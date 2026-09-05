# Duplicate-order detection

The customer PO reference is the existing commission_number field: intake creates one order per commission, while a ticket can cover several commissions. Matching uses the same client ID and commission number, ignoring letter case and surrounding spaces. Punctuation, leading zeros and internal spaces remain significant. Empty references never match. Demo and real orders are separate.

Intake and revalidation persist a duplicate_order error. Detail responses include live duplicate_orders with links in the UI, so existing records are covered without a data backfill. Approval, XML generation and sending recheck the database and return 409 on duplicates, even when customer master-data validation is disabled. Failed gates clear approval and record status changes in Change History. No automatic merge, deletion or override is provided.

Compare the source documents, correct an incorrectly extracted commission number, or reject the extra order. Refresh the remaining order after resolving another record. Rejected records with generated XML still count as matches because export evidence must not disappear through rejection. Standard client access rules apply to the containing order and matches never cross client boundaries.

The check happens after extracting enough information to identify a commission; it does not prevent the cost of extracting a resent email. Existing Message-ID deduplication remains in place. Direct database writes bypass application gates. Migration 202609050010 adds a customer/demo lookup index and does not change order data.
