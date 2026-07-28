"""Availability arithmetic over the anchor ledger and Stock Reservation Entries.

`available_qty` is the API the execution-gating child needs for the material-availability
gate (URS-W1-008/009): on-hand from the anchor ledger *minus* live reservations, so that
stock promised to a draft document or an order is not counted as available. Reservations
live on the anchor `Stock Reservation Entry` (URS-W1-023/025), which keeps a single
reservation mechanism (ADR-008).
"""

from __future__ import annotations

from decimal import Decimal

import frappe


def _to_decimal(value: object) -> Decimal:
	return Decimal(str(value or 0))


def ledger_balance(
	item: str, warehouse: str, batch_no: str | None = None, consider_expired: bool = False
) -> Decimal:
	"""On-hand quantity from the anchor Stock Ledger (the single quantity truth).

	Batch-level when `batch_no` is given, otherwise the item's warehouse balance. Batch
	balances exclude expired batches by default (as the anchor does); disposal ordering
	sets `consider_expired` so an expired-but-physically-present batch still appears in the
	FEFO/LEFO order — the expiry hard stop (URS-W1-013/030) is a separate gate.
	"""
	if batch_no:
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		return _to_decimal(
			get_batch_qty(
				batch_no=batch_no,
				warehouse=warehouse,
				item_code=item,
				for_stock_levels=consider_expired,
			)
		)
	from erpnext.stock.utils import get_stock_balance

	return _to_decimal(get_stock_balance(item, warehouse))


def reserved_qty(item: str, warehouse: str) -> Decimal:
	"""Sum of live reservations (draft + submitted, not cancelled) for item+warehouse.

	Mirrors Qcadoo's reservedQuantity on a resource (`ResourceFields.RESERVED_QUANTITY`)
	but expressed as the anchor SRE outstanding reserved quantity.
	"""
	rows = frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"item_code": item,
			"warehouse": warehouse,
			"docstatus": ["<", 2],
			"status": ["!=", "Cancelled"],
		},
		fields=["reserved_qty", "delivered_qty"],
	)
	total = Decimal("0")
	for row in rows:
		total += _to_decimal(row.reserved_qty) - _to_decimal(row.delivered_qty)
	return total


def available_qty(item: str, warehouse: str) -> Decimal:
	"""Available quantity = on-hand ledger balance minus live reservations (URS-W1-008).

	On-hand stays untouched by reservations; only *available* shrinks — exactly the
	Qcadoo distinction between quantity and availableQuantity on a resource.

	W2-3 subtracts the quantity held by Blocked and Quarantined batches as well, so such
	stock is neither reservable nor counted as available (URS-W2-010 AC-2); the exclusion
	itself is decided in one place, `rheinwerk_mes.genealogy.blocking`.
	"""
	from rheinwerk_mes.genealogy.blocking import excluded_qty

	return ledger_balance(item, warehouse) - reserved_qty(item, warehouse) - excluded_qty(item, warehouse)
