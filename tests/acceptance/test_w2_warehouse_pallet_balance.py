"""W2-8 pallet balances reconciled against the anchor ledger.

TC-W2-033 (URS-W2-025) — a pallet (Handling Unit) shows up in the warehouse pallet balance
    at its storage location with its content quantity (AC-1), and the single-truth
    reconciliation reports any divergence between the summed Handling-Unit content and the
    anchor ledger balance, the ledger always being the quantity truth (AC-2).
"""

from __future__ import annotations

COMPANY = "Rheinwerk Chemie GmbH"
RM = "RM Lager Nord - RWC"
ITEM = "RW-CHM-0001"
BATCH = "BATCH-A-0001"
LOCATION = "NORD-A-01-01"

PALLET_BALANCE = "rheinwerk_mes.warehouse.pallet_balance.pallet_balance"
RECONCILIATION = "rheinwerk_mes.warehouse.pallet_balance.reconciliation"
LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"


def _handling_unit(site, qty: float):
	return site.get_doc(
		{
			"doctype": "Handling Unit",
			"hu_type": "Palette",
			"warehouse": RM,
			"storage_location": LOCATION,
			"company": COMPANY,
			"contents": [{"item": ITEM, "batch_no": BATCH, "qty": qty, "uom": "Kg"}],
		}
	).insert(ignore_permissions=True)


def test_tc_w2_033_pallet_appears_in_the_balance_at_its_location(site):
	"""TC-W2-033 (URS-W2-025 AC-1): a pallet holding 500 kg of BATCH-A-0001 (20 × 25 kg
	sacks) at NORD-A-01-01 appears in the warehouse pallet balance at that location with a
	content of 500 kg — the reference view over the ledger, not a second quantity store."""
	pallet_balance = site.get_attr(PALLET_BALANCE)
	unit = _handling_unit(site, 500)

	rows = [row for row in pallet_balance(RM) if row["handling_unit"] == unit.name]
	assert len(rows) == 1
	row = rows[0]
	assert row["storage_location"] == LOCATION
	assert row["item"] == ITEM
	assert row["batch_no"] == BATCH
	assert row["qty"] == 500.0
	assert row["reconciliation_flag"] is False


def test_tc_w2_033_reconciliation_reports_divergence_ledger_is_truth(site):
	"""TC-W2-033 (URS-W2-025 AC-2): over-declaring a pallet's content by 600 kg beyond the
	ledger balance makes reconciliation report the divergence with the ledger as the
	authoritative quantity and the signed difference — it never rewrites the ledger.

	The seeded pallet HU-000123 mirrors the 500 kg ledger balance exactly, so the warehouse
	reconciles cleanly at the baseline; the divergence asserted here is the delta the extra
	600 kg pallet introduces on top of that consistent baseline."""
	reconciliation = site.get_attr(RECONCILIATION)
	ledger_balance = site.get_attr(LEDGER_BALANCE)

	# Baseline is consistent: the seeded pallet's content equals the ledger, so the summed
	# Handling-Unit quantity for the batch equals the ledger balance (no divergence yet).
	assert reconciliation(RM) == []
	ledger_qty = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))

	_handling_unit(site, 600)

	divergences = [row for row in reconciliation(RM) if row["batch_no"] == BATCH]
	assert len(divergences) == 1
	row = divergences[0]
	assert row["ledger_qty"] == ledger_qty
	assert row["handling_unit_qty"] == ledger_qty + 600.0
	assert row["difference"] == 600.0
