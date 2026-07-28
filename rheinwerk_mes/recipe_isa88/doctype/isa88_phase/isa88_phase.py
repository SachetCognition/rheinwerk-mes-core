"""`ISA88 Phase` — one phase of an ISA-88 unit procedure (W2-6, URS-W2-020).

A phase is either a material charge (a `material` drawn from the recipe's BOM, in `uom`)
or a process step (a `duration_min`, e.g. "Mischen 30 min"). It is a child row of
`ISA88 Recipe`, grouped onto its unit procedure by the `unit_procedure` key.
"""

from __future__ import annotations

from frappe.model.document import Document


class ISA88Phase(Document):
	pass
