"""Durable store for every message crossing the group-ERP boundary (URS-W3-011/012/014).

One row per contract message, in either direction: the row *is* the error queue, the
unmapped-accounts hold queue, the outbound outbox and the idempotency ledger. Rows are
written only by `rheinwerk_mes.integration.boundary.queues`; the DocType itself is
read-only in the Desk (`in_create`) so a message can never be edited into a lie.
"""

from __future__ import annotations

from frappe.model.document import Document


class BoundaryMessage(Document):
	pass
