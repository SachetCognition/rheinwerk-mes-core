"""Stocktaking DocType controller — delegates to `warehouse.stocktaking` (W2-8)."""

from __future__ import annotations

from frappe.model.document import Document

from rheinwerk_mes.warehouse import journey, stocktaking


class Stocktaking(Document):
	def before_insert(self) -> None:
		journey.set_initial_state(self, stocktaking.JOURNEY)

	def validate(self) -> None:
		stocktaking.validate(self)

	def on_update(self) -> None:
		stocktaking.on_update(self)
