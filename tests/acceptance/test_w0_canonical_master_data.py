"""W0 canonical Item master and UoM conversions.

TC-W0-004 (URS-W0-003) — canonical Item master with `legacy_refs`.
TC-W0-005 (URS-W0-004) — item-level UoM conversion resolution and factor-0 rejection.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# The offline CI job has no Frappe installed, so app modules are resolved through the
# connected site (`frappe.get_attr`) rather than imported at collection time.
RESOLVE_TO_STOCK_UOM = "rheinwerk_mes.manufacturing_core.uom.resolve_to_stock_uom"

COMPANY = "Rheinwerk Chemie GmbH"
RM_WAREHOUSE = "RM Lager Nord - RWC"

EXPECTED_ITEMS = {
	"RW-CHM-0001": ("Rheinol 40 Basisharz", "Kg", "Sack", 25.0),
	"RW-CHM-0002": ("Additiv K7", "Kg", "Pail", 5.0),
	"RW-CHM-0003": ("Rheinol 40 Compound", "Kg", None, None),
}


def test_tc_w0_004_items_exist_with_canonical_values(site):
	"""TC-W0-004 step 1+2 (URS-W0-003 AC-1): the three fixture items are on the anchor
	`Item` DocType with German names, kg stock UoM and their pack conversions."""
	for item_code, (item_name, stock_uom, pack_uom, pack_factor) in EXPECTED_ITEMS.items():
		item = site.get_doc("Item", item_code)
		assert item.item_name == item_name
		assert item.stock_uom == stock_uom
		if pack_uom:
			packs = {row.uom: row.conversion_factor for row in item.uoms}
			assert packs[pack_uom] == pack_factor


def test_tc_w0_004_legacy_refs_expose_source_identifiers(site):
	"""TC-W0-004 step 3 (URS-W0-003 AC-2): migrated items carry their source-system
	identifier in `legacy_refs`, which is a `rheinwerk_mes` Custom Field."""
	assert site.db.exists(
		"Custom Field", {"dt": "Item", "fieldname": "legacy_refs", "module": "Manufacturing Core"}
	)
	refs = {
		row.source_system: row.source_identifier for row in site.get_doc("Item", "RW-CHM-0001").legacy_refs
	}
	assert refs["Qcadoo"] == "P-000123"
	assert refs["OFBiz"] == "RHEINOL-40-BASE"
	assert site.get_doc("Item", "RW-CHM-0003").legacy_refs


def test_tc_w0_005_pack_quantity_resolves_without_drift(site):
	"""TC-W0-005 step 1 (URS-W0-004 AC-1): 20 sack of RW-CHM-0001 resolves to exactly
	500 kg, and 1 pail of RW-CHM-0002 to exactly 5 kg."""
	resolve_to_stock_uom = site.get_attr(RESOLVE_TO_STOCK_UOM)
	assert resolve_to_stock_uom("RW-CHM-0001", 20, "Sack") == Decimal("500")
	assert resolve_to_stock_uom("RW-CHM-0002", 1, "Pail") == Decimal("5")
	assert resolve_to_stock_uom("RW-CHM-0001", "0.1", "Sack") == Decimal("2.5")


def pack_receipt(site, qty, uom, item_code="RW-CHM-0001", conversion_factor=None):
	"""Material receipt of `qty` `uom` — the fixture transaction quantities are entered on."""
	row = {
		"item_code": item_code,
		"qty": qty,
		"uom": uom,
		"t_warehouse": RM_WAREHOUSE,
		"basic_rate": 100,
	}
	if conversion_factor is not None:
		row["conversion_factor"] = conversion_factor
	return site.get_doc(
		{
			"doctype": "Stock Entry",
			"company": COMPANY,
			"stock_entry_type": "Material Receipt",
			"items": [row],
		}
	)


def test_tc_w0_005_pack_quantity_on_a_transaction_resolves_to_stock_uom(site):
	"""TC-W0-005 step 1 (URS-W0-004 AC-1): a fixture stock transaction entered in packs
	resolves to the stock UoM through the item-level conversion — 20 sack = 500 kg."""
	entry = pack_receipt(site, 20, "Sack")
	entry.insert()
	assert entry.items[0].conversion_factor == 25.0
	assert entry.items[0].stock_uom == "Kg"
	assert entry.items[0].transfer_qty == 500.0


def test_tc_w0_005_transaction_factor_cannot_deviate_from_the_item_conversion(site):
	"""TC-W0-005 (URS-W0-004 AC-1): resolution is deterministic — a factor supplied on the
	transaction row is replaced by the item-level one instead of being trusted."""
	entry = pack_receipt(site, 20, "Sack", conversion_factor=30)
	entry.insert()
	assert entry.items[0].conversion_factor == 25.0
	assert entry.items[0].transfer_qty == 500.0


def test_tc_w0_005_pack_uom_without_item_conversion_is_rejected(site):
	"""TC-W0-005 (URS-W0-004): resolution is item-level only — a pack UoM the item carries
	no conversion for cannot be booked, whatever global conversions exist."""
	with pytest.raises(site.ValidationError) as excinfo:
		pack_receipt(site, 1, "Pail").insert()
	assert "keine Umrechnung" in str(excinfo.value)


def test_tc_w0_005_zero_conversion_factor_is_rejected(site):
	"""TC-W0-005 step 2 (URS-W0-004 AC-2): a conversion factor of 0 fails validation."""
	item = site.get_doc("Item", "RW-CHM-0002")
	item.uoms[0].conversion_factor = 0
	with pytest.raises(site.ValidationError) as excinfo:
		item.save()
	assert "Umrechnungsfaktor" in str(excinfo.value)


def test_tc_w0_005_stock_uom_conversion_must_be_one(site):
	"""TC-W0-005 (URS-W0-004): the stock UoM may only convert to itself with factor 1."""
	item = site.get_doc("Item", "RW-CHM-0002")
	item.append("uoms", {"uom": item.stock_uom, "conversion_factor": 2})
	with pytest.raises(site.ValidationError):
		item.save()
