"""W1-6 reservations over the anchor Stock Reservation Entry and the availability API.

TC-W1-024 (URS-W1-023) — a draft outbound Stock Entry creates a draft-flagged reservation;
    on-hand is unchanged and available qty drops by the reserved amount.
TC-W1-025 (URS-W1-024) — deleting/rejecting the draft releases the reservation and restores
    available qty.
TC-W1-026 (URS-W1-025) — order-level reservations are Stock Reservation Entries against the
    Work Order and are released together via `release_for_order`.
"""

from __future__ import annotations

from decimal import Decimal

AVAILABLE_QTY = "rheinwerk_mes.warehouse.availability.available_qty"
LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"
RESERVE_FOR_ORDER = "rheinwerk_mes.warehouse.reservations.reserve_for_order"
RELEASE_FOR_ORDER = "rheinwerk_mes.warehouse.reservations.release_for_order"
RELEASE_FOR_DRAFT = "rheinwerk_mes.warehouse.reservations.release_for_draft_document"

COMPANY = "Rheinwerk Chemie GmbH"
RM = "RM Lager Nord - RWC"
WORK_ORDER = "PO-2026-0001"


def _draft_issue(site, item, qty, batch_no):
	doc = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": COMPANY,
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"s_warehouse": RM,
					"uom": "Kg",
					"use_serial_batch_fields": 1,
					"batch_no": batch_no,
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def test_tc_w1_024_draft_document_makes_reservation(site):
	"""TC-W1-024 (URS-W1-023): saving a draft Material Issue for 200 kg creates a
	draft-flagged Stock Reservation Entry; on-hand stays put while available qty falls by
	200 (Qcadoo "draft makes reservation")."""
	available_qty = site.get_attr(AVAILABLE_QTY)
	ledger_balance = site.get_attr(LEDGER_BALANCE)

	on_hand_before = ledger_balance("RW-CHM-0001", RM)
	available_before = available_qty("RW-CHM-0001", RM)

	doc = _draft_issue(site, "RW-CHM-0001", 200, "BATCH-A-0001")

	sres = site.get_all(
		"Stock Reservation Entry",
		filters={"voucher_type": "Stock Entry", "voucher_no": doc.name},
		fields=["reserved_qty", "draft_reservation", "docstatus"],
	)
	assert len(sres) == 1
	assert sres[0].draft_reservation == 1
	assert sres[0].docstatus == 0
	assert Decimal(str(sres[0].reserved_qty)) == Decimal("200")

	assert ledger_balance("RW-CHM-0001", RM) == on_hand_before
	assert available_qty("RW-CHM-0001", RM) == available_before - Decimal("200")


def test_tc_w1_025_deleting_draft_releases_reservation(site):
	"""TC-W1-025 (URS-W1-024): deleting the draft document cancels its draft reservation and
	restores available qty."""
	available_qty = site.get_attr(AVAILABLE_QTY)
	available_before = available_qty("RW-CHM-0001", RM)

	doc = _draft_issue(site, "RW-CHM-0001", 200, "BATCH-A-0001")
	assert available_qty("RW-CHM-0001", RM) == available_before - Decimal("200")

	site.delete_doc("Stock Entry", doc.name, force=True, ignore_permissions=True)

	assert not site.get_all(
		"Stock Reservation Entry", filters={"voucher_type": "Stock Entry", "voucher_no": doc.name}
	)
	assert available_qty("RW-CHM-0001", RM) == available_before


def test_tc_w1_025_release_for_draft_api_is_idempotent(site):
	"""TC-W1-025 (URS-W1-024): the explicit release API cancels a draft's reservations and
	reports how many it released; a second call is a no-op."""
	release_for_draft_document = site.get_attr(RELEASE_FOR_DRAFT)
	doc = _draft_issue(site, "RW-CHM-0001", 100, "BATCH-A-0001")
	assert release_for_draft_document(doc.name) == 1
	assert release_for_draft_document(doc.name) == 0


def test_tc_w1_026_order_level_reservations_on_stock_reservation_entry(site):
	"""TC-W1-026 (URS-W1-025): reserving a Work Order creates Stock Reservation Entries
	against that order (visible from it), reduces available qty for the reserved component,
	and `release_for_order` clears them all."""
	available_qty = site.get_attr(AVAILABLE_QTY)
	reserve_for_order = site.get_attr(RESERVE_FOR_ORDER)
	release_for_order = site.get_attr(RELEASE_FOR_ORDER)

	available_before = available_qty("RW-CHM-0001", RM)

	created = reserve_for_order(WORK_ORDER)
	assert created >= 1

	order_sres = site.get_all(
		"Stock Reservation Entry",
		filters={"voucher_type": "Work Order", "voucher_no": WORK_ORDER},
		fields=["item_code", "reserved_qty", "warehouse"],
	)
	reserved_items = {row.item_code for row in order_sres}
	assert "RW-CHM-0001" in reserved_items
	assert available_qty("RW-CHM-0001", RM) < available_before

	# Idempotent: a second reserve adds nothing.
	assert reserve_for_order(WORK_ORDER) == 0

	released = release_for_order(WORK_ORDER)
	assert released == len(order_sres)
	assert not site.get_all(
		"Stock Reservation Entry", filters={"voucher_type": "Work Order", "voucher_no": WORK_ORDER}
	)
	assert available_qty("RW-CHM-0001", RM) == available_before
