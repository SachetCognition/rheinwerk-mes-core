"""W2-8 stocktaking journey (persona W. Braun) posting onto the anchor ledger.

TC-W2-034 (URS-W2-026) — the `draft → in progress → accepted` journey, driven by the
    warehouse clerk W. Braun, posts a correcting Material Issue for a count below book so
    the ledger ends at the counted quantity and then becomes immutable (AC-1); a difference
    leaves the ledger consistent — the correction equals exactly book − counted, nothing is
    invented or lost; only one open stocktaking is allowed per warehouse (AC-2).
"""

from __future__ import annotations

import frappe
import pytest

COMPANY = "Rheinwerk Chemie GmbH"
RM = "RM Lager Nord - RWC"
ITEM = "RW-CHM-0001"
BATCH = "BATCH-A-0001"
LOCATION = "NORD-A-01-01"
BRAUN = "w.braun@rheinwerk-chemie.example"

LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"


def _stocktaking(site, counted: float):
	book = float(site.get_attr(LEDGER_BALANCE)(ITEM, RM, BATCH, consider_expired=True))
	return site.get_doc(
		{
			"doctype": "Stocktaking",
			"warehouse": RM,
			"company": COMPANY,
			"lines": [
				{
					"item": ITEM,
					"batch_no": BATCH,
					"storage_location": LOCATION,
					"book_qty": book,
					"counted_qty": counted,
					"uom": "Kg",
				}
			],
		}
	).insert(ignore_permissions=True)


def test_tc_w2_034_accepting_a_short_count_posts_a_correcting_issue(site):
	"""TC-W2-034 (URS-W2-026 AC-1): W. Braun counts BATCH-A-0001 at 495 kg against a 500 kg
	book quantity; accepting posts a correcting 5 kg Material Issue (Qcadoo RELEASE) so the
	ledger reads 495 kg, and the accepted stocktaking is then immutable."""
	ledger_balance = site.get_attr(LEDGER_BALANCE)
	before = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))

	doc = _stocktaking(site, 495)
	site.set_user(BRAUN)
	doc.reload()
	doc.state = "In Progress"
	doc.save()
	doc.state = "Accepted"
	doc.save()
	doc.reload()

	assert doc.state == "Accepted"
	correction = doc.lines[0].correction_stock_entry
	assert correction
	assert site.db.get_value("Stock Entry", correction, "purpose") == "Material Issue"

	after = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))
	assert after == 495.0
	# Ledger consistency: the correction is exactly the counted − book difference; the
	# stocktaking neither invents nor loses quantity.
	assert before - after == 5.0

	# The accepted record is immutable (Qcadoo FINISHED terminal).
	doc.reason = "nachträgliche Änderung"
	with pytest.raises(frappe.ValidationError):
		doc.save()


def test_tc_w2_034_only_one_open_stocktaking_per_warehouse(site):
	"""TC-W2-034 (URS-W2-026 AC-2): with an open (draft/in-progress) stocktaking for RM
	Lager Nord, creating a second stocktaking for the same warehouse is refused."""
	_stocktaking(site, 500)
	with pytest.raises(frappe.ValidationError):
		site.get_doc({"doctype": "Stocktaking", "warehouse": RM, "company": COMPANY}).insert(
			ignore_permissions=True
		)


def test_tc_w2_034_illegal_transition_is_refused(site):
	"""TC-W2-034 (URS-W2-026): the journey mirrors Qcadoo StocktakingState — a draft may not
	jump straight to Accepted without passing through In Progress."""
	doc = _stocktaking(site, 500)
	doc.state = "Accepted"
	with pytest.raises(frappe.ValidationError):
		doc.save()
