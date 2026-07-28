"""Warehouse → group-ERP account mapping for boundary GL postings (URS-W3-012).

The MES holds no financial ledger of record: this map is the only place where a warehouse's
stock and offset account codes in the group ERP are maintained. A warehouse without a map
entry holds its postings instead of emitting a wrong one (AC-2).
"""

from __future__ import annotations

from frappe.model.document import Document


class GroupERPAccountMap(Document):
	pass
