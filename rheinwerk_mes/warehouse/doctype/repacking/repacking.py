"""Repacking DocType controller — delegates to `warehouse.repacking` (W2-8)."""

from __future__ import annotations

from frappe.model.document import Document

from rheinwerk_mes.warehouse import journey, repacking


class Repacking(Document):
	def before_insert(self) -> None:
		journey.set_initial_state(self, repacking.JOURNEY)

	def validate(self) -> None:
		repacking.validate(self)

	def on_update(self) -> None:
		repacking.on_update(self)
