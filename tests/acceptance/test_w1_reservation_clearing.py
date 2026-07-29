"""W1-2 reservation clearing on the anchor Work Order.

TC-W1-010 (URS-W1-009) — an order that holds an active reservation releases it when the
    planner declines the order: the Stock Reservation Entry is cancelled and the reserved
    quantity returns to available (Qcadoo `OrderStatesListenerServicePFTD.clearReservations`
    parity).

Site-backed: needs the W1 foundation (URS-W1-001 `exec_state` machine, URS-W1-025
order-level reservations) and the programme seed installed. Where a precondition is absent
the test skips rather than fails, so it is meaningful only on a fully seeded W1 site.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

COMPANY = "Rheinwerk Chemie GmbH"
WORK_ORDER = "PO-2026-0002"
ITEM = "RW-CHM-0002"
DECLINE_REASON = "Kunde hat den Auftrag storniert (Test TC-W1-010)."


def _active_order_reservations(site, work_order, item):
	return site.get_all(
		"Stock Reservation Entry",
		filters={
			"voucher_type": "Work Order",
			"voucher_no": work_order,
			"item_code": item,
			"docstatus": ["<", 2],
		},
		fields=["name", "warehouse", "reserved_qty", "docstatus"],
	)


def _available_qty(site, item, warehouse):
	"""Available = on-hand ledger balance minus still-active reservations."""
	available_qty = _maybe_attr(site, "rheinwerk_mes.warehouse.availability.available_qty")
	if available_qty is not None:
		return Decimal(str(available_qty(item, warehouse)))

	ledger_balance = _maybe_attr(site, "rheinwerk_mes.warehouse.availability.ledger_balance")
	on_hand = (
		Decimal(str(ledger_balance(item, warehouse)))
		if ledger_balance is not None
		else Decimal(
			str(site.db.get_value("Bin", {"item_code": item, "warehouse": warehouse}, "actual_qty") or 0)
		)
	)
	reserved = sum(
		Decimal(str(row.reserved_qty)) for row in _active_order_reservations(site, WORK_ORDER, item)
	)
	return on_hand - reserved


def _maybe_attr(site, dotted_path):
	try:
		return site.get_attr(dotted_path)
	except Exception:
		return None


def _decline(site, work_order):
	transition = _maybe_attr(site, "rheinwerk_mes.manufacturing_core.exec_state.transition")
	if transition is None:
		pytest.skip("exec_state transition entrypoint not installed (URS-W1-001 dependency)")
	transition(work_order, "Declined", reason=DECLINE_REASON)


def test_tc_w1_010_reservations_cleared_on_decline(site):
	"""TC-W1-010 (URS-W1-009): declining PO-2026-0002 with a reason cancels its active
	50 kg RW-CHM-0002 reservation and returns the quantity to available."""
	if not site.db.exists("Work Order", WORK_ORDER):
		pytest.skip(f"seed fixture {WORK_ORDER} not present (URS-W1-025 dependency)")

	reservations = _active_order_reservations(site, WORK_ORDER, ITEM)
	if not reservations:
		pytest.skip(f"{WORK_ORDER} holds no active {ITEM} reservation (URS-W1-025 dependency)")

	warehouse = reservations[0].warehouse
	reserved_total = sum(Decimal(str(row.reserved_qty)) for row in reservations)
	assert reserved_total == Decimal("50")

	available_before = _available_qty(site, ITEM, warehouse)

	_decline(site, WORK_ORDER)

	assert not _active_order_reservations(site, WORK_ORDER, ITEM)
	assert _available_qty(site, ITEM, warehouse) == available_before + Decimal("50")
