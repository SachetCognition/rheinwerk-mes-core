"""Handling Unit content row — a reference to stock, never an authoritative quantity.

The `qty` column mirrors what the anchor ledger records for the item/batch in the
handling unit's warehouse; it exists for identification and reconciliation only
(URS-W1-018). See `handling_unit.py` for the reconciliation-flag logic.
"""

from __future__ import annotations

from frappe.model.document import Document


class HandlingUnitContent(Document):
	pass
