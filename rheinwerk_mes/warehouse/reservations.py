"""Draft- and order-level reservations on the anchor Stock Reservation Entry.

Reconciles Qcadoo's "draft makes reservation" semantics
(`ReservationsService.java:81-247`, `SachetCognition/Chem_mes@master`) with the ERPNext
`Stock Reservation Entry` (SRE). Qcadoo creates a reservation row for every position of a
not-yet-accepted (draft) material document, reducing the resource's availableQuantity
without moving on-hand stock, and deletes it when the position/document is removed. Here
the same behaviour is expressed as SREs against the anchor documents so order- and
document-level reservations share one mechanism (ADR-008 / CDM-06):

* draft outbound Stock Entry  → `draft_reservation`-flagged SRE (URS-W1-023/024)
* production order            → SRE against the Work Order (URS-W1-025)

Draft-document SREs are kept in Draft (docstatus 0): they must reduce *available* qty
(computed in `availability.available_qty`) without posting the anchor's reserved-in-bin
side-effects that submission would trigger, exactly like a Qcadoo draft reservation.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.warehouse.availability import ledger_balance

#: Custom voucher type (Property Setter extends SRE.voucher_type) used for the draft
#: outbound Stock Entry that owns a draft reservation.
DRAFT_VOUCHER_TYPE = "Stock Entry"

#: Stock Entry purposes whose source rows draw stock and therefore reserve on draft.
_OUTBOUND_PURPOSES = {
	"Material Issue",
	"Material Transfer",
	"Material Transfer for Manufacture",
	"Manufacture",
	"Send to Subcontractor",
}


def _company(warehouse: str) -> str:
	return frappe.db.get_value("Warehouse", warehouse, "company")


def _stock_uom(item: str) -> str:
	return frappe.db.get_value("Item", item, "stock_uom")


def _draft_reservation_enabled(warehouse: str) -> bool:
	"""Per-warehouse toggle (`draft_makes_reservation` Custom Field), mirroring Qcadoo's
	`reservationsEnabledForDocumentPositions`."""
	return bool(frappe.db.get_value("Warehouse", warehouse, "draft_makes_reservation"))


def _make_reservation(
	*,
	item: str,
	warehouse: str,
	qty: float,
	voucher_type: str,
	voucher_no: str,
	voucher_detail_no: str,
	draft_reservation: bool,
) -> str:
	"""Create a Draft SRE reserving `qty` of `item` in `warehouse`; returns its name."""
	sre = frappe.get_doc(
		{
			"doctype": "Stock Reservation Entry",
			"item_code": item,
			"warehouse": warehouse,
			"voucher_type": voucher_type,
			"voucher_no": voucher_no,
			"voucher_detail_no": voucher_detail_no,
			"available_qty": float(ledger_balance(item, warehouse)),
			"voucher_qty": qty,
			"reserved_qty": qty,
			"stock_uom": _stock_uom(item),
			"company": _company(warehouse),
			"draft_reservation": 1 if draft_reservation else 0,
		}
	)
	sre.flags.ignore_permissions = True
	sre.insert(ignore_permissions=True)
	return sre.name


# --- draft outbound document (URS-W1-023 / URS-W1-024) --------------------------------


def reserve_for_draft_document(stock_entry) -> int:
	"""Sync draft reservations for a draft outbound Stock Entry ("draft makes reservation").

	Idempotent: one SRE per source item row, refreshed when the row quantity changes and
	dropped when the row disappears. Only warehouses with `draft_makes_reservation` on
	participate, matching Qcadoo's per-document reservation toggle.
	Baseline: `ReservationsService.createReservationFromDocumentPosition` (only non-accepted
	documents reserve; ReservationsService.java:98-121).
	"""
	if stock_entry.docstatus != 0 or stock_entry.purpose not in _OUTBOUND_PURPOSES:
		return 0

	live_rows: set[str] = set()
	created = 0
	for row in stock_entry.items:
		warehouse = row.s_warehouse
		if not warehouse or not _draft_reservation_enabled(warehouse):
			continue
		live_rows.add(row.name)
		existing = frappe.get_all(
			"Stock Reservation Entry",
			filters={
				"voucher_type": DRAFT_VOUCHER_TYPE,
				"voucher_no": stock_entry.name,
				"voucher_detail_no": row.name,
				"draft_reservation": 1,
				"docstatus": 0,
			},
			pluck="name",
		)
		if existing:
			sre = frappe.get_doc("Stock Reservation Entry", existing[0])
			sre.warehouse = warehouse
			sre.item_code = row.item_code
			sre.voucher_qty = row.qty
			sre.reserved_qty = row.qty
			sre.available_qty = float(ledger_balance(row.item_code, warehouse))
			sre.save(ignore_permissions=True)
		else:
			_make_reservation(
				item=row.item_code,
				warehouse=warehouse,
				qty=row.qty,
				voucher_type=DRAFT_VOUCHER_TYPE,
				voucher_no=stock_entry.name,
				voucher_detail_no=row.name,
				draft_reservation=True,
			)
			created += 1

	# Drop reservations for rows that no longer exist on the draft.
	for name in frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"voucher_type": DRAFT_VOUCHER_TYPE,
			"voucher_no": stock_entry.name,
			"draft_reservation": 1,
			"docstatus": 0,
			"voucher_detail_no": ["not in", list(live_rows) or [""]],
		},
		pluck="name",
	):
		frappe.delete_doc("Stock Reservation Entry", name, force=True, ignore_permissions=True)
	return created


def release_for_draft_document(stock_entry_name: str) -> int:
	"""Cancel/delete the draft reservations of a draft document on delete or reject.

	Baseline: `ReservationsService.deleteReservationFromDocumentPosition`
	(ReservationsService.java:225-241) — reservations vanish with the draft positions,
	restoring availableQuantity. Returns the number of reservations released.
	"""
	names = frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"voucher_type": DRAFT_VOUCHER_TYPE,
			"voucher_no": stock_entry_name,
			"draft_reservation": 1,
		},
		fields=["name", "docstatus"],
	)
	for row in names:
		if row.docstatus == 1:
			frappe.get_doc("Stock Reservation Entry", row.name).cancel()
		else:
			frappe.delete_doc("Stock Reservation Entry", row.name, force=True, ignore_permissions=True)
	return len(names)


# --- order-level reservations (URS-W1-025 / URS-W1-009) -------------------------------


def reserve_for_order(work_order: str) -> int:
	"""Reserve each required component of a Work Order as an SRE against the order.

	Anchor-native order-level reservation (ADR-008): quantities come from the order's
	required items and are reserved in the order's WIP/source warehouse. Idempotent — a
	component already reserved for the order is skipped. Returns the number created.
	"""
	wo = frappe.get_doc("Work Order", work_order)
	created = 0
	for req in wo.get("required_items") or []:
		source = _order_source_warehouse(req, wo)
		if not source:
			continue
		if frappe.db.exists(
			"Stock Reservation Entry",
			{
				"voucher_type": "Work Order",
				"voucher_no": work_order,
				"item_code": req.item_code,
				"warehouse": source,
				"docstatus": ["<", 2],
			},
		):
			continue
		_make_reservation(
			item=req.item_code,
			warehouse=source,
			qty=req.required_qty,
			voucher_type="Work Order",
			voucher_no=work_order,
			voucher_detail_no=req.name,
			draft_reservation=False,
		)
		created += 1
	return created


def _order_source_warehouse(required_item, work_order) -> str | None:
	"""Warehouse a component is reserved from: its own source if that holds stock, else the
	order's WIP/source warehouse. Reservations are only meaningful where stock exists."""
	candidates = [
		required_item.get("source_warehouse"),
		work_order.get("wip_warehouse"),
		work_order.get("source_warehouse"),
	]
	for warehouse in candidates:
		if warehouse and ledger_balance(required_item.item_code, warehouse) > 0:
			return warehouse
	return required_item.get("source_warehouse") or work_order.get("wip_warehouse")


def release_for_order(work_order: str) -> int:
	"""Release all reservations held by a Work Order (URS-W1-009 / URS-W1-024).

	Called by the order state machine when an order is Declined or Abandoned
	(`OrderStatesListenerServicePFTD.java:633`). Cancels submitted SREs and deletes draft
	ones; returns the number released.
	"""
	rows = frappe.get_all(
		"Stock Reservation Entry",
		filters={"voucher_type": "Work Order", "voucher_no": work_order, "docstatus": ["<", 2]},
		fields=["name", "docstatus"],
	)
	for row in rows:
		if row.docstatus == 1:
			frappe.get_doc("Stock Reservation Entry", row.name).cancel()
		else:
			frappe.delete_doc("Stock Reservation Entry", row.name, force=True, ignore_permissions=True)
	return len(rows)


# --- Stock Entry doc_event hooks ------------------------------------------------------


def on_stock_entry_update(doc, method=None) -> None:
	"""`Stock Entry.on_update` — keep draft reservations in sync while the doc is a draft."""
	if doc.docstatus == 0:
		reserve_for_draft_document(doc)


def on_stock_entry_trash(doc, method=None) -> None:
	"""`Stock Entry.on_trash` — a deleted draft releases its reservations (URS-W1-024)."""
	release_for_draft_document(doc.name)


def on_stock_entry_submit(doc, method=None) -> None:
	"""`Stock Entry.on_submit` — the real posting supersedes any draft reservation."""
	release_for_draft_document(doc.name)


def on_stock_entry_cancel(doc, method=None) -> None:
	"""`Stock Entry.on_cancel` — release any lingering draft reservations."""
	release_for_draft_document(doc.name)
