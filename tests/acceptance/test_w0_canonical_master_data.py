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
