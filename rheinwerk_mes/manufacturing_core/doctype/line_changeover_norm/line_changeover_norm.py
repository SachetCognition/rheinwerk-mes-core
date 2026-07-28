"""Line changeover norm between two products on a line (W3-2 · URS-W3-007).

An empty `to_item` means "changeover to any other product", the Qcadoo group case, while a
norm naming the same product twice is the inter-batch flush between two orders of that
product. The matching precedence lives in `scheduling.changeover`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class LineChangeoverNorm(Document):
	def validate(self) -> None:
		if (self.changeover_min or 0) < 0:
			frappe.throw(_("Die Umrüstzeit darf nicht negativ sein."), title=_("Umrüstnorm ungültig"))
