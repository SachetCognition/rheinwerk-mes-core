"""TJ/TPZ time norm per operation and work centre (W3-2 · URS-W3-006).

TPZ is the setup/preparatory time of the operation, TJ the unit production time per kg;
`scheduling.realization_time` turns both into whole minutes exactly as Qcadoo does.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class OperationTimeNorm(Document):
	def validate(self) -> None:
		if (self.tpz_min or 0) < 0 or (self.tj_min_per_unit or 0) < 0:
			frappe.throw(_("TPZ und TJ dürfen nicht negativ sein."), title=_("Zeitnorm ungültig"))
		if (self.workstations_count or 1) < 1:
			frappe.throw(
				_("Die Anzahl der Arbeitsplätze muss mindestens 1 betragen."),
				title=_("Zeitnorm ungültig"),
			)
