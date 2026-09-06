# Customer clarification drafts

Order details provides Prepare clarification draft. GET /api/v1/orders/{id}/clarification-draft uses the authenticated user's client access and fresh, read-only validation; it does not clear approvals, release reservations, change status or call an email/AI provider.

Recipient defaults to a usable Reply-To, then sender, then customer default address. Review it before use. Questions use explicit customer-facing templates for missing information, product/price corrections, address/customer mismatches and duplicate POs. Stock, account setup and extraction diagnostics are internal review notes, never part of the copied message. The older intake draft now uses the same wording templates.

Recipient, subject and body are editable. Copy reviewed draft copies those fields only. No email is sent and edits are not persisted across navigation or refresh. Regenerate replaces local edits. Saved order changes mark the draft stale and block copying until regeneration; changes made in another session require refreshing the order. No customer questions produces an empty message rather than an invented request. Sending and durable draft storage remain separate future work.
