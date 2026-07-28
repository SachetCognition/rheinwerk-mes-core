"""`ISA88 Unit Procedure` — one unit procedure of an ISA-88 recipe (W2-6, URS-W2-020).

A unit procedure binds one anchor Routing `operation` executed at one `workstation`
(the work centre). The equipment working-volume ceiling `max_working_qty` is fetched from
the work centre's `rw_max_working_qty` Custom Field and consumed by recipe scaling
(`recipe_isa88.scaling`, URS-W2-021 AC-2). It is a child row of `ISA88 Recipe`.
"""

from __future__ import annotations

from frappe.model.document import Document


class ISA88UnitProcedure(Document):
	pass
