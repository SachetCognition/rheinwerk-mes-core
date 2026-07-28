"""Per-warehouse disposal algorithm applied to the anchor ledger (URS-W1-020).

Qcadoo carries the disposal algorithm (FIFO/LIFO/FEFO/LEFO) on the *warehouse*
(`WarehouseAlgorithm.java:26-27`), unlike the anchor's single global stock setting.
This module reads that per-warehouse strategy (a Custom Field on the anchor Warehouse),
builds resource mappings from the batch balances in the ledger, and orders them through
the pure parity function in `contracts.picking_order`, so the site path and the offline
`CHAR-FEFO-PICK-01` contract share one ordering rule.

Semantics: `ResourceManagementServiceImpl.java:1015-1027,1207-1220`
(`getResourcesForWarehouseProductAndAlgorithm`, `SachetCognition/Chem_mes@master`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import frappe
from frappe.utils import getdate

from rheinwerk_mes.warehouse.availability import ledger_balance
from rheinwerk_mes.warehouse.contracts import normalise_algorithm, picking_order

DEFAULT_ALGORITHM = "FIFO"


def warehouse_algorithm(warehouse: str) -> str:
	"""The warehouse's disposal strategy (Custom Field `disposal_method`), FIFO default."""
	value = frappe.db.get_value("Warehouse", warehouse, "disposal_method")
	return normalise_algorithm(value or DEFAULT_ALGORITHM)


def _fmt_de(value: object) -> str:
	parsed: date = getdate(value)
	return parsed.strftime("%d.%m.%Y")


def _intake_date(batch: str) -> date:
	"""Resource intake time used by FIFO/LIFO — the batch's manufacturing date, else its
	creation timestamp (`ResourceFields.TIME`)."""
	values = frappe.db.get_value("Batch", batch, ["manufacturing_date", "creation"], as_dict=True)
	if values and values.get("manufacturing_date"):
		return getdate(values["manufacturing_date"])
	return getdate(values["creation"]) if values else getdate()


def resources_for_warehouse(item: str, warehouse: str) -> list[dict]:
	"""Ledger-backed resource mappings (one per batch with a positive balance).

	The mapping shape is exactly the `contracts.picking_order` / characterisation-fixture
	shape: `batch`, `expiration_date` (DD.MM.YYYY), `available_quantity`, `time`.
	"""
	batches = frappe.get_all(
		"Batch",
		filters={"item": item},
		fields=["name", "expiry_date"],
	)
	from rheinwerk_mes.genealogy.blocking import is_pickable

	resources: list[dict] = []
	for batch in batches:
		# W2-3: Blocked and Quarantined stock never becomes a picking candidate
		# (URS-W2-010); the predicate is owned by `rheinwerk_mes.genealogy.blocking`.
		if not is_pickable(batch.name):
			continue
		balance = ledger_balance(item, warehouse, batch.name, consider_expired=True)
		if balance <= 0:
			continue
		resources.append(
			{
				"batch": batch.name,
				"expiration_date": _fmt_de(batch.expiry_date) if batch.expiry_date else "31.12.9999",
				"available_quantity": float(balance),
				"time": _fmt_de(_intake_date(batch.name)),
			}
		)
	return resources


def picking_order_for_warehouse(item: str, warehouse: str) -> tuple[str, ...]:
	"""Batch identifiers for `item` in `warehouse`, ordered by its disposal algorithm."""
	resources = resources_for_warehouse(item, warehouse)
	return picking_order(resources, warehouse_algorithm(warehouse))


def allocate(item: str, warehouse: str, qty: float) -> list[tuple[str, Decimal]]:
	"""Greedy batch allocation of `qty` following the warehouse disposal order.

	Returns `(batch, allocated_qty)` pairs; the first pair is the batch the algorithm
	selects first (URS-W1-020 AC-1/AC-2). Allocation stops once demand is met; a shortfall
	simply yields a partial allocation (the caller decides how to gate it).
	"""
	remaining = Decimal(str(qty))
	balances = {
		r["batch"]: Decimal(str(r["available_quantity"])) for r in resources_for_warehouse(item, warehouse)
	}
	allocations: list[tuple[str, Decimal]] = []
	for batch in picking_order_for_warehouse(item, warehouse):
		if remaining <= 0:
			break
		take = min(remaining, balances.get(batch, Decimal("0")))
		if take > 0:
			allocations.append((batch, take))
			remaining -= take
	return allocations
