"""W1-5 Handling Unit reference layer and warehouse-scoped Storage Location tree.

TC-W1-019 (URS-W1-018) — the Handling Unit is an identification/grouping object; it never
    writes a Stock Ledger Entry and cannot become a second quantity store.
TC-W1-020 (URS-W1-019) — Storage Locations are a per-warehouse tree; a location of one
    warehouse cannot be attached to a handling unit (or child location) of another.
"""

from __future__ import annotations

import pytest

RM = "RM Lager Nord - RWC"
FG = "FG Lager Süd - RWC"
LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"


def _make_handling_unit(site, warehouse, contents, storage_location="NORD-A-01-01"):
	return site.get_doc(
		{
			"doctype": "Handling Unit",
			"hu_type": "Palette",
			"warehouse": warehouse,
			"storage_location": storage_location,
			"contents": contents,
		}
	)


def test_tc_w1_019_handling_unit_is_not_a_second_quantity_store(site):
	"""TC-W1-019 (URS-W1-018): saving a Handling Unit that references 500 kg of
	BATCH-A-0001 posts no Stock Ledger Entry and leaves the anchor ledger balance
	untouched — the ledger stays the single source of quantity truth."""
	ledger_balance = site.get_attr(LEDGER_BALANCE)
	before = ledger_balance("RW-CHM-0001", RM)

	hu = _make_handling_unit(
		site,
		RM,
		[{"item": "RW-CHM-0001", "batch_no": "BATCH-A-0001", "qty": 500, "uom": "Kg"}],
	)
	hu.insert(ignore_permissions=True)

	assert hu.reconciliation_flag == 0
	assert ledger_balance("RW-CHM-0001", RM) == before
	assert not site.get_all("Stock Ledger Entry", filters={"voucher_type": "Handling Unit"})
	assert not site.get_all("Stock Ledger Entry", filters={"voucher_no": hu.name})


def test_tc_w1_019_over_declared_content_raises_reconciliation_flag(site):
	"""TC-W1-019 (URS-W1-018): if a Handling Unit declares more than the ledger records, it
	raises a reconciliation flag rather than overriding the ledger — it can never invent
	quantity."""
	hu = _make_handling_unit(
		site,
		RM,
		[{"item": "RW-CHM-0001", "batch_no": "BATCH-A-0001", "qty": 999999, "uom": "Kg"}],
	)
	hu.insert(ignore_permissions=True)
	assert hu.reconciliation_flag == 1


def test_tc_w1_020_storage_location_is_warehouse_scoped(site):
	"""TC-W1-020 (URS-W1-019): NORD-A-01-01 belongs to RM Lager Nord; a child location in a
	different warehouse is rejected."""
	assert site.db.get_value("Storage Location", "NORD-A-01-01", "warehouse") == RM
	child = site.get_doc(
		{
			"doctype": "Storage Location",
			"storage_location_name": "SUED-BAD-01",
			"warehouse": FG,
			"parent_storage_location": "NORD-A-01-01",
			"is_group": 0,
		}
	)
	with pytest.raises(site.exceptions.ValidationError):
		child.insert(ignore_permissions=True)


def test_tc_w1_020_handling_unit_rejects_foreign_warehouse_location(site):
	"""TC-W1-020 (URS-W1-019): a handling unit in FG Lager Süd cannot be assigned the
	RM Lager Nord location NORD-A-01-01."""
	hu = _make_handling_unit(site, FG, [], storage_location="NORD-A-01-01")
	with pytest.raises(site.exceptions.ValidationError):
		hu.insert(ignore_permissions=True)
