"""W0 canonical Item master.

TC-W0-004 (URS-W0-003) — canonical Item master with `legacy_refs`.
"""

from __future__ import annotations

EXPECTED_ITEMS = {
	"RW-CHM-0001": ("Rheinol 40 Basisharz", "Kg", "Sack", 25.0),
	"RW-CHM-0002": ("Additiv K7", "Kg", "Pail", 5.0),
	"RW-CHM-0003": ("Rheinol 40 Compound", "Kg", None, None),
}

EXPECTED_LEGACY_REFS = {
	"RW-CHM-0001": {"Qcadoo": "P-000123", "OFBiz": "RHEINOL-40-BASE"},
	"RW-CHM-0002": {"Qcadoo": "P-000124"},
	"RW-CHM-0003": {"ERPNext Legacy": "COMPOUND-40"},
}


def test_tc_w0_004_items_exist_with_canonical_values(site):
	"""URS-W0-003 AC-1: the three fixture items are on the anchor `Item` DocType with
	German names, kg stock UoM and their pack conversions."""
	for item_code, (item_name, stock_uom, pack_uom, pack_factor) in EXPECTED_ITEMS.items():
		item = site.get_doc("Item", item_code)
		assert item.item_name == item_name
		assert item.stock_uom == stock_uom
		if pack_uom:
			packs = {row.uom: row.conversion_factor for row in item.uoms}
			assert packs[pack_uom] == pack_factor


def test_tc_w0_004_legacy_refs_are_a_custom_field_on_the_anchor(site):
	"""URS-W0-003 AC-2: `legacy_refs` extends the anchor `Item` as a `rheinwerk_mes`
	Custom Field — the anchor DocType itself is never forked."""
	assert site.db.exists(
		"Custom Field",
		{"dt": "Item", "fieldname": "legacy_refs", "module": "Manufacturing Core"},
	)


def test_tc_w0_004_legacy_refs_expose_source_identifiers(site):
	"""URS-W0-003 AC-2: every migrated item carries its source-system identifier
	(Qcadoo product number / ERPNext item_code / OFBiz productId)."""
	for item_code, expected in EXPECTED_LEGACY_REFS.items():
		refs = {
			row.source_system: row.source_identifier for row in site.get_doc("Item", item_code).legacy_refs
		}
		assert refs == expected
