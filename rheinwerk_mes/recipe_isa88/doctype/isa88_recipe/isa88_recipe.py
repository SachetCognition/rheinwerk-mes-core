"""`ISA88 Recipe` — the ISA-88 procedural view over the governed BOM/Routing pair (W2-6).

Requirements: URS-W2-020 (recipe → unit procedure → phase hierarchy over the anchor BOM +
Routing, without forking either), URS-W2-021 (scaling — see `recipe_isa88.scaling`),
URS-W2-022 (execution under the W1-4 `gov_state` governance). White space in all three
legacy systems (dossier §6.3): designed from the URS and IEC 61512-1, pinned by
characterisation-free acceptance tests. Design: `docs/design/W2-isa88.md`.

The controller only keeps the recipe internally consistent and derived fields fresh; the
scaling arithmetic and equipment/rounding gates live in `recipe_isa88.scaling` so they are
callable offline.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from rheinwerk_mes.recipe_isa88 import structure


class ISA88Recipe(Document):
	def validate(self) -> None:
		self._sync_anchor_fields()
		structure.validate_structure(self)

	def _sync_anchor_fields(self) -> None:
		"""Fill routing / output UoM from the linked BOM and output item when left empty."""
		if not self.bom:
			return
		if not self.routing:
			self.routing = frappe.db.get_value("BOM", self.bom, "routing")
		if not self.item:
			self.item = frappe.db.get_value("BOM", self.bom, "item")
		if not self.batch_uom and self.item:
			self.batch_uom = frappe.db.get_value("Item", self.item, "stock_uom")
