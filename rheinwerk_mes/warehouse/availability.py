"""Availability arithmetic over the anchor stock ledger and Stock Reservation Entries.

`available_qty` is the quantity the material-availability gate judges against
(URS-W1-008): on-hand from the anchor ledger *minus* live reservations, so stock promised
to another order or to a draft document does not count as available. On-hand itself stays
untouched by reservations — the same distinction Qcadoo draws between a resource's
`quantity` and its `availableQuantity`.

Reservations live on the anchor `Stock Reservation Entry` (URS-W1-023/025), keeping a
single reservation mechanism; the ledger stays the single quantity truth (URS-W1-021).
"""

from __future__ import annotations

from decimal import Decimal

import frappe

RESERVATION_DOCTYPE = "Stock Reservation Entry"


def _to_decimal(value: object) -> Decimal:
	return Decimal(str(value or 0))


def ledger_balance(item: str, warehouse: str) -> Decimal:
	"""On-hand quantity of `item` in `warehouse` from the anchor stock ledger."""
	from erpnext.stock.utils import get_stock_balance

	return _to_decimal(get_stock_balance(item, warehouse))


def reserved_qty(item: str, warehouse: str, exclude_voucher: tuple[str, str] | None = None) -> Decimal:
	"""Outstanding live reservations (draft and submitted, not cancelled) for item+warehouse.

	`exclude_voucher` is a `(voucher_type, voucher_no)` pair whose reservations are left out,
	so a voucher is not made to compete with the stock it reserved for itself.
	"""
	filters: dict[str, object] = {
		"item_code": item,
		"warehouse": warehouse,
		"docstatus": ["<", 2],
		"status": ["!=", "Cancelled"],
	}
	rows = frappe.get_all(
		RESERVATION_DOCTYPE,
		filters=filters,
		fields=["reserved_qty", "delivered_qty", "voucher_type", "voucher_no"],
	)
	total = Decimal("0")
	for row in rows:
		if exclude_voucher and (row.voucher_type, row.voucher_no) == exclude_voucher:
			continue
		total += _to_decimal(row.reserved_qty) - _to_decimal(row.delivered_qty)
	return total


def available_qty(item: str, warehouse: str, exclude_voucher: tuple[str, str] | None = None) -> Decimal:
	"""On-hand ledger balance minus live reservations (URS-W1-008 AC-3)."""
	return ledger_balance(item, warehouse) - reserved_qty(item, warehouse, exclude_voucher)
