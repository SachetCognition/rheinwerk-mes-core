"""W1-3 — the substrate's own hard stops still fire through the Rheinwerk workflow.

Covers TC-W1-011 (URS-W1-010 over-production), TC-W1-012 (URS-W1-011 stopped-order
freeze), TC-W1-013 (URS-W1-012 closed order is terminal) and TC-W1-014 (URS-W1-013
expired-batch consumption and picking stops, hard stop per the URS-W1-030 estate policy).

These are *Adopt* behaviours: nothing here re-implements or weakens an anchor rule — the
tests drive ERPNext through our app (hooks and the `exec_state` workflow installed) and
assert the anchor refusals are intact. The single exception is documented: the anchor's
Stock-Ledger expiry throw exempts `voucher_type == "Stock Entry"`
(`stock_ledger_entry.py:287-299`), so consuming an expired batch is refused by
`rheinwerk_mes.execution_gating.expiry` instead — a hook, not a fork.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
anchor_stops = pytest.importorskip("rheinwerk_mes.execution_gating.anchor_stops")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

from test_w1_gating_support import (  # noqa: E402  (import after the substrate check)
	COMPANY,
	COMPONENT_A,
	EXPIRED_BATCH,
	FIRST_ORDER,
	RM_WAREHOUSE,
	SECOND_ORDER,
	require_fixture,
	stock_ledger_count,
	submitted_order,
)

CLERK_USER = "w.braun@rheinwerk-chemie.example"


# --------------------------------------------------------------------------------------
# TC-W1-011 — over-production hard stop (URS-W1-010)
# --------------------------------------------------------------------------------------


def test_overproduction_is_refused_and_writes_no_ledger_entry(site):
	"""URS-W1-010 · TC-W1-011 — 510 kg against a 500 kg order at 0 % allowance is refused."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	order = submitted_order(site, FIRST_ORDER)
	assert site.db.get_single_value("Manufacturing Settings", "overproduction_percentage_for_work_order") == 0
	before = stock_ledger_count(site)

	entry = site.get_doc(make_stock_entry(order.name, "Manufacture", 510))
	with pytest.raises(frappe.ValidationError) as excinfo:
		entry.insert(ignore_permissions=True)
		entry.submit()

	assert "510" in str(excinfo.value) and "500" in str(excinfo.value)
	assert stock_ledger_count(site) == before, "an over-production attempt writes no SLE"
	assert site.db.get_value("Work Order", order.name, "produced_qty") == 0


def test_production_within_the_order_quantity_is_allowed(site):
	"""URS-W1-010 · TC-W1-011 — the stop is an upper bound, not a block on all output."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	order = submitted_order(site, FIRST_ORDER)
	entry = site.get_doc(make_stock_entry(order.name, "Manufacture", 100))
	entry.insert(ignore_permissions=True)
	entry.submit()

	assert entry.docstatus == 1
	assert site.db.get_value("Work Order", order.name, "produced_qty") == 100


# --------------------------------------------------------------------------------------
# TC-W1-012 — stopped-order freeze (URS-W1-011)
# --------------------------------------------------------------------------------------


def test_job_card_against_a_stopped_order_is_refused(site):
	"""URS-W1-011 · TC-W1-012 — a MIX job card on a stopped Work Order is refused."""
	from erpnext.manufacturing.doctype.work_order.work_order import stop_unstop

	order = submitted_order(site, FIRST_ORDER)
	stop_unstop(order.name, "Stopped")
	assert site.db.get_value("Work Order", order.name, "status") == "Stopped"

	card = site.get_doc(
		{
			"doctype": "Job Card",
			"work_order": order.name,
			"operation": "MIX",
			"workstation": "MIX-01",
			"for_quantity": 10,
			"company": COMPANY,
			"posting_date": frappe.utils.nowdate(),
		}
	)
	with pytest.raises(frappe.ValidationError) as excinfo:
		card.insert(ignore_permissions=True)
		card.submit()

	assert "Work Order" in str(excinfo.value)
	assert site.db.count("Job Card", {"work_order": order.name, "docstatus": 1}) == 0


# --------------------------------------------------------------------------------------
# TC-W1-013 — closed order is terminal (URS-W1-012)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["Stopped", "Resumed"])
def test_closed_order_can_neither_be_stopped_nor_reopened(site, action):
	"""URS-W1-012 · TC-W1-013 — both stop and re-open of a Closed order are refused."""
	from erpnext.manufacturing.doctype.work_order.work_order import stop_unstop

	order = submitted_order(site, SECOND_ORDER)
	site.db.set_value("Work Order", order.name, "status", "Closed", update_modified=False)

	with pytest.raises(frappe.ValidationError) as excinfo:
		stop_unstop(order.name, action)

	assert "Closed" in str(excinfo.value)
	assert site.db.get_value("Work Order", order.name, "status") == "Closed"


# --------------------------------------------------------------------------------------
# TC-W1-014 — expired-batch consumption and picking stops (URS-W1-013)
# --------------------------------------------------------------------------------------


def _issue_from_expired_batch(site, qty: float = 5.0):
	return site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": COMPANY,
			"items": [
				{
					"item_code": COMPONENT_A,
					"qty": qty,
					"s_warehouse": RM_WAREHOUSE,
					"uom": "Kg",
					"use_serial_batch_fields": 1,
					"batch_no": EXPIRED_BATCH,
				}
			],
		}
	)


def test_issuing_an_expired_batch_is_refused_without_any_posting(site):
	"""URS-W1-013 · TC-W1-014 step 1 — issuing 5 kg from BATCH-A-0002 is refused, no SLE."""
	require_fixture(site, "Batch", EXPIRED_BATCH)
	before = stock_ledger_count(site)
	site.set_user(CLERK_USER) if site.db.exists("User", CLERK_USER) else None

	with pytest.raises(frappe.ValidationError) as excinfo:
		_issue_from_expired_batch(site).insert(ignore_permissions=True)

	message = str(excinfo.value)
	site.set_user("Administrator")
	assert EXPIRED_BATCH in message
	assert "30.06.2026" in message, "expiry rendered German-first DD.MM.YYYY"
	assert "Regel:" in message and "Behebung:" in message, "hard gate names rule and resolution"
	assert stock_ledger_count(site) == before


def test_expired_batch_refusal_is_logged_immutably(site):
	"""URS-W1-013 · URS-W1-033 · TC-W1-014 — the refusal lands in the gate audit log."""
	require_fixture(site, "Batch", EXPIRED_BATCH)
	with pytest.raises(frappe.ValidationError):
		_issue_from_expired_batch(site).insert(ignore_permissions=True)

	entries = audit.entries_for("Batch", EXPIRED_BATCH)
	assert [entry for entry in entries if entry["gate"] == "expiry_gate"]


def test_transferring_an_expired_batch_is_refused_too(site):
	"""URS-W1-013 · TC-W1-014 — the gate covers every outward purpose the anchor exempts.

	`serial_batch_bundle_service.validate_serialized_batch` skips its expiry throw for the
	Stock Entry purposes *Material Issue* and *Material Transfer* (`:110-112`), which is the
	substrate gap this gate closes for both.
	"""
	require_fixture(site, "Batch", EXPIRED_BATCH)
	entry = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Transfer",
			"company": COMPANY,
			"items": [
				{
					"item_code": COMPONENT_A,
					"qty": 5,
					"s_warehouse": RM_WAREHOUSE,
					"t_warehouse": "FG Lager Süd - RWC",
					"uom": "Kg",
					"use_serial_batch_fields": 1,
					"batch_no": EXPIRED_BATCH,
				}
			],
		}
	)

	with pytest.raises(frappe.ValidationError) as excinfo:
		entry.insert(ignore_permissions=True)

	assert EXPIRED_BATCH in str(excinfo.value)


def test_the_gate_ignores_inward_rows(site):
	"""URS-W1-013 · TC-W1-014 — the policy refuses *consumption*; intake rows are not judged.

	Intake of an expired batch is separately refused by the anchor itself
	(`serial_batch_bundle_service.py:132-147`), so this gate deliberately stays out of it.
	"""
	expiry = pytest.importorskip("rheinwerk_mes.execution_gating.expiry")
	receipt = frappe._dict(
		doctype="Stock Entry",
		name=None,
		purpose="Material Receipt",
		posting_date="2026-07-28",
		items=[frappe._dict(item_code=COMPONENT_A, batch_no=EXPIRED_BATCH, t_warehouse=RM_WAREHOUSE)],
	)

	assert expiry.enforce_batch_expiry(receipt) is None


def test_pick_list_with_an_expired_batch_is_refused_on_save(site):
	"""URS-W1-013 · TC-W1-014 step 2 — the anchor's own pick-list expiry stop still fires."""
	require_fixture(site, "Batch", EXPIRED_BATCH)
	order = submitted_order(site, FIRST_ORDER)
	pick_list = site.get_doc(
		{
			"doctype": "Pick List",
			"company": COMPANY,
			"purpose": "Material Transfer for Manufacture",
			"work_order": order.name,
			"locations": [
				{
					"item_code": COMPONENT_A,
					"warehouse": RM_WAREHOUSE,
					"batch_no": EXPIRED_BATCH,
					"qty": 5,
					"stock_qty": 5,
					"picked_qty": 5,
					"uom": "Kg",
					"stock_uom": "Kg",
					"conversion_factor": 1,
				}
			],
		}
	)

	with pytest.raises(frappe.ValidationError) as excinfo:
		pick_list.insert(ignore_permissions=True)

	assert EXPIRED_BATCH in str(excinfo.value)


# --------------------------------------------------------------------------------------
# Declaration of the adopted stops (feeds the W1-10 behaviour record)
# --------------------------------------------------------------------------------------


def test_every_adopted_hard_stop_is_declared_with_its_urs_tc_and_verdict():
	"""URS-W1-010…013 — the registry names the anchor source, TC and Parity/Divergence."""
	assert len(anchor_stops.ANCHOR_HARD_STOPS) == 4
	for stop in anchor_stops.ANCHOR_HARD_STOPS:
		assert stop.urs.startswith("URS-W1-")
		assert stop.tc.startswith("TC-W1-")
		assert stop.anchor_source
		assert stop.verdict in {"Parity", "Divergence"}
	expiry = anchor_stops.by_id("ANCHOR-EXPIRED-BATCH")
	assert expiry.verdict == "Divergence" and "URS-W1-030" in expiry.note
