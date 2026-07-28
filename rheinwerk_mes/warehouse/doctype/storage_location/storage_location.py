"""Warehouse-scoped storage-location tree (URS-W1-019, CDM-03).

Re-implements the Qcadoo `materialFlowResources` storageLocation model
(`ResourceFields.STORAGE_LOCATION`) as a Frappe nested set below the anchor
Warehouse. Locations never hold quantity — they are addressing objects assignable
to handling units and batch allocations; the anchor Stock Ledger stays the single
source of stock truth (ADR-005).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class StorageLocation(NestedSet):
	nsm_parent_field = "parent_storage_location"

	def validate(self) -> None:
		self._validate_warehouse_scope()

	def _validate_warehouse_scope(self) -> None:
		"""A child location must live in the same warehouse as its parent (URS-W1-019 AC-2)."""
		if not self.parent_storage_location:
			return
		parent_warehouse = frappe.db.get_value("Storage Location", self.parent_storage_location, "warehouse")
		if parent_warehouse and parent_warehouse != self.warehouse:
			frappe.throw(
				_("Lagerplatz {0} gehört zu Lager {1} und kann nicht unter {2} liegen.").format(
					self.name or self.storage_location_name, self.warehouse, parent_warehouse
				),
				title=_("Lager stimmt nicht überein"),
			)
