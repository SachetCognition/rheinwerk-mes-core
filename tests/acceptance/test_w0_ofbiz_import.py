"""Plant B (OFBiz) master-data import on the substrate — URS-W0-010.

TC-W0-011 step 1 (AC-1) — after the extractor runs and the import executes: the item exists,
exactly one Workstation is created for the machine FixedAsset, and no accounting record.

Site-backed: skipped where no Frappe site with a seeded ERPNext substrate is available.
"""

from __future__ import annotations

MIGRATION = "rheinwerk_mes.integration.migration"


def import_plant_b(substrate):
	extract = substrate.get_attr(f"{MIGRATION}.cli.extract_source")("ofbiz")
	return extract, substrate.get_attr(f"{MIGRATION}.importer.import_extract")(extract)


def test_tc_w0_011_item_exists_after_import(substrate):
	"""TC-W0-011 step 1 (AC-1): the Product mapping to RW-CHM-0003 lands on the anchor
	`Item` with its OFBiz unit of measure translated, not defaulted."""
	import_plant_b(substrate)

	item = substrate.get_doc("Item", "RW-CHM-0003")
	assert item.stock_uom == "Kg"
	assert item.item_name == "Rheinol 40 Compound"


def test_tc_w0_011_machine_asset_imports_as_one_workstation_without_accounting(substrate):
	"""TC-W0-011 step 1 (AC-1, CDM-08): the machine FixedAsset becomes exactly one
	Workstation, and the import creates no `Asset` record for it."""
	assets_before = substrate.db.count("Asset")

	extract, result = import_plant_b(substrate)

	assert result.imported["work_centre"] == 1
	assert result.documents["Workstation"] == ["Extruder 01"]
	assert substrate.db.exists("Workstation", "Extruder 01")
	assert substrate.db.count("Asset") == assets_before


def test_tc_w0_011_unmappable_uom_is_not_imported(substrate):
	"""TC-W0-011 step 2 (AC-2): the reported Product is absent from the target — the
	exceptions report is the only place it appears."""
	extract, result = import_plant_b(substrate)

	assert [exception.source_identifier for exception in extract.exceptions] == ["RHEINOL-40-LB"]
	assert not substrate.db.exists("Item", "RW-CHM-0009")


def test_import_is_idempotent(substrate):
	"""A second run updates in place instead of duplicating master data."""
	extract, first = import_plant_b(substrate)
	_, second = import_plant_b(substrate)

	assert second.imported == first.imported
	assert substrate.db.count("Workstation", {"name": "Extruder 01"}) == 1
