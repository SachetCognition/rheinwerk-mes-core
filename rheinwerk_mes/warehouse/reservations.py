"""Order-level reservations over the anchor Stock Reservation Entry.

An order-level reservation is a Stock Reservation Entry (SRE) held against the anchor
`Work Order` (`voucher_type = "Work Order"`), reducing a component's available quantity
without moving on-hand stock (ADR-008 / CDM-06). This module owns the *release* side of
that lifecycle (URS-W1-009): when an order no longer needs its reserved stock, every SRE
it holds is cancelled/deleted and the quantity returns to available.

Legacy baseline (semantics only, never ported): Qcadoo
`OrderStatesListenerServicePFTD.clearReservations` (:129-131), invoked on the transitions
into *declined* and *abandoned* (`OrderStatesListenerAspectPFTD:68-81`,
`SachetCognition/Chem_mes@master`).

The *creation* of order-level reservations (`reserve_for_order`, auto-reserve on
acceptance) is URS-W1-025 and lands with that requirement; this module deliberately holds
only what URS-W1-009 needs so the decline/abandon side effect has a stable API to call.
"""

from __future__ import annotations

import frappe

#: The anchor voucher type an order-level reservation is booked against.
ORDER_VOUCHER_TYPE = "Work Order"


def order_reservations(work_order: str) -> list:
	"""Active (not-yet-cancelled) Stock Reservation Entries held by `work_order`."""
	return frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"voucher_type": ORDER_VOUCHER_TYPE,
			"voucher_no": work_order,
			"docstatus": ["<", 2],
		},
		fields=["name", "docstatus"],
	)


def release_for_order(work_order: str) -> int:
	"""Release every reservation held by a Work Order (URS-W1-009).

	Called by the order state machine's post-transition side effect when an order reaches
	Declined or Abandoned (`OrderStatesListenerServicePFTD.java:633`). Submitted SREs are
	cancelled and draft ones deleted, so the reserved quantity returns to available.
	Idempotent — a second call finds nothing left to release. Returns the number released.
	"""
	released = 0
	for row in order_reservations(work_order):
		if row.docstatus == 1:
			frappe.get_doc("Stock Reservation Entry", row.name).cancel()
		else:
			frappe.delete_doc("Stock Reservation Entry", row.name, force=True, ignore_permissions=True)
		released += 1
	return released
