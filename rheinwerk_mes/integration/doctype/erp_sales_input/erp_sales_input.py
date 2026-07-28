"""Inbound demand from the group ERP, keyed by its external order reference (URS-W3-010).

The record is the MES-side sales input the planner turns into a Production Plan
(URS-W3-001); the external reference is unique, which is what makes redelivery of the same
orders-in message idempotent.
"""

from __future__ import annotations

from frappe.model.document import Document


class ERPSalesInput(Document):
	pass
