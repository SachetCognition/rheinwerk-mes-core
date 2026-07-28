"""Handling Unit — pallet/load-unit identification layer (URS-W1-018, CDM-03).

Re-implements the Qcadoo lot-level pallet affordance (`ResourceFields.PALLET_NUMBER`,
`ResourceFields.TYPE_OF_LOAD_UNIT`, `ResourceFields.STORAGE_LOCATION`) as an integrity
DocType that *references* stock. It is deliberately **not** a parallel quantity store:
the Handling Unit never writes a Stock Ledger Entry, and its content quantities are
reference values reconciled against the anchor ledger — the ledger stays the single
source of quantity truth (ADR-005, dossier §7 implication 4). A divergence sets a
reconciliation flag rather than creating a second, authoritative balance.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document

from rheinwerk_mes.warehouse.availability import ledger_balance


class HandlingUnit(Document):
	def validate(self) -> None:
		self._validate_storage_location_scope()
		self.set_reconciliation_flag()

	def _validate_storage_location_scope(self) -> None:
		"""The assigned storage location must belong to this handling unit's warehouse
		(URS-W1-019 AC-2 — locations are warehouse-scoped)."""
		if not self.storage_location:
			return
		location_warehouse = frappe.db.get_value("Storage Location", self.storage_location, "warehouse")
		if location_warehouse and location_warehouse != self.warehouse:
			frappe.throw(
				_("Lagerplatz {0} gehört zu Lager {1}, nicht zu {2}.").format(
					self.storage_location, location_warehouse, self.warehouse
				),
				title=_("Lager stimmt nicht überein"),
			)

	def set_reconciliation_flag(self) -> None:
		"""Flag the unit when its referenced quantities exceed the anchor ledger balance.

		The handling unit may hold part of a batch (content ≤ ledger); it can never hold
		*more* than the ledger records in its warehouse — that would make it a second
		quantity store, which URS-W1-018 forbids. Such a divergence raises this flag for a
		clerk to reconcile; it never overrides the ledger.
		"""
		declared: dict[tuple[str, str | None], Decimal] = defaultdict(lambda: Decimal("0"))
		for row in self.contents or []:
			declared[(row.item, row.batch_no)] += Decimal(str(row.qty or 0))
		self.reconciliation_flag = 0
		for (item, batch_no), declared_qty in declared.items():
			if declared_qty > ledger_balance(item, self.warehouse, batch_no):
				self.reconciliation_flag = 1
				break
