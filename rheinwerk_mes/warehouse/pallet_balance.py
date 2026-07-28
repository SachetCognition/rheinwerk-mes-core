"""Pallet balances and single-truth reconciliation (W2-8 · URS-W2-025).

A *pallet balance* lists the Handling Units of a warehouse with their storage location,
type and content — the per-location pallet view Qcadoo builds over its resources grouped
by `storageLocation` and `palletNumber` (`materialFlowResources` `palletBalance`, dossier
ch. 3.1 §B.3; `storageLocation.xml:37-54` shows the pallet/position/resource relations
this report reads). Rheinwerk expresses it over the W1 `Handling Unit` reference layer
(ADR-005/CDM-03) rather than a second quantity store.

Single-truth constraint (URS-W2-025 AC-2): the anchor Stock Ledger is the quantity truth
and a Handling Unit is only a reference. `reconciliation()` lists every `(item, batch,
warehouse)` where the summed Handling-Unit content diverges from the ledger balance, so a
clerk can correct the reference — the report never rewrites the ledger from the pallets.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import frappe

from rheinwerk_mes.warehouse.availability import ledger_balance


def _decimal(value: object) -> Decimal:
	return Decimal(str(value or 0))


@frappe.whitelist()
def pallet_balance(warehouse: str) -> list[dict[str, Any]]:
	"""Handling Units of `warehouse` with location, type and content rows (AC-1).

	One row per Handling-Unit content line, so a pallet holding several batches lists each
	batch at its location. Rows are ordered by storage location then handling unit, the
	order a clerk walks the aisle.
	"""
	units = frappe.get_all(
		"Handling Unit",
		filters={"warehouse": warehouse},
		fields=["name", "hu_type", "storage_location", "reconciliation_flag"],
		order_by="storage_location asc, name asc",
	)
	rows: list[dict[str, Any]] = []
	for unit in units:
		contents = frappe.get_all(
			"Handling Unit Content",
			filters={"parent": unit.name, "parenttype": "Handling Unit"},
			fields=["item", "batch_no", "qty", "uom"],
			order_by="idx asc",
		)
		for content in contents:
			rows.append(
				{
					"handling_unit": unit.name,
					"hu_type": unit.hu_type,
					"storage_location": unit.storage_location,
					"item": content.item,
					"batch_no": content.batch_no,
					"qty": float(_decimal(content.qty)),
					"uom": content.uom,
					"reconciliation_flag": bool(unit.reconciliation_flag),
				}
			)
	return rows


def _handling_unit_totals(warehouse: str) -> dict[tuple[str, str | None], Decimal]:
	"""Sum of Handling-Unit content per `(item, batch)` for `warehouse`."""
	totals: dict[tuple[str, str | None], Decimal] = defaultdict(lambda: Decimal("0"))
	for unit in frappe.get_all("Handling Unit", filters={"warehouse": warehouse}, pluck="name"):
		for content in frappe.get_all(
			"Handling Unit Content",
			filters={"parent": unit, "parenttype": "Handling Unit"},
			fields=["item", "batch_no", "qty"],
		):
			totals[(content.item, content.batch_no)] += _decimal(content.qty)
	return totals


@frappe.whitelist()
def reconciliation(warehouse: str) -> list[dict[str, Any]]:
	"""Divergent `(item, batch)` rows for `warehouse` — ledger is truth (AC-2).

	A divergence is any `(item, batch)` whose summed Handling-Unit content differs from the
	anchor ledger balance in the warehouse. Both an over-declaration (pallets claim more
	than the ledger holds) and an under-declaration (unpalletised stock the pallets do not
	account for) are reported, with the signed difference. Expired-but-present batches are
	included so the reference view stays complete.
	"""
	totals = _handling_unit_totals(warehouse)
	# Batches that carry a ledger balance in the warehouse but no Handling-Unit content
	# must still surface as divergences, so union the two key sets.
	keys = set(totals)
	for item, batch in _ledger_batch_keys(warehouse):
		keys.add((item, batch))

	divergences: list[dict[str, Any]] = []
	for item, batch in sorted(keys, key=lambda key: (key[0] or "", key[1] or "")):
		hu_qty = totals.get((item, batch), Decimal("0"))
		ledger_qty = ledger_balance(item, warehouse, batch, consider_expired=True) if batch else _decimal(0)
		if hu_qty != ledger_qty:
			divergences.append(
				{
					"item": item,
					"batch_no": batch,
					"warehouse": warehouse,
					"handling_unit_qty": float(hu_qty),
					"ledger_qty": float(ledger_qty),
					"difference": float(hu_qty - ledger_qty),
				}
			)
	return divergences


def _ledger_batch_keys(warehouse: str) -> set[tuple[str, str]]:
	"""`(item, batch)` pairs that have any Handling-Unit reference in `warehouse`.

	Reconciliation compares the reference layer against the ledger, so its key universe is
	the batches the pallets name; a ledger batch never referenced by a pallet is simply
	stock that is not on a pallet and is out of the pallet report's scope.
	"""
	pairs: set[tuple[str, str]] = set()
	for unit in frappe.get_all("Handling Unit", filters={"warehouse": warehouse}, pluck="name"):
		for content in frappe.get_all(
			"Handling Unit Content",
			filters={"parent": unit, "parenttype": "Handling Unit"},
			fields=["item", "batch_no"],
		):
			if content.batch_no:
				pairs.add((content.item, content.batch_no))
	return pairs
