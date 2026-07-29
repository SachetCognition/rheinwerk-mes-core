"""OFBiz FixedAsset machine-group migration → canonical Work Centre (URS-W0-005 AC-2).

TC-W0-006 step 2: a machine imported from an OFBiz FixedAsset group becomes a `Workstation`
and the MES creates no asset-ledger record; non-machine assets (buildings/property) are
skipped entirely (CDM-08, ADR-010, ADR-002).
"""

from __future__ import annotations

MACHINE = "EXTRUDER-01"
NON_MACHINE = "BUERO-NORD"


def test_tc_w0_006_ofbiz_machine_group_becomes_workstation(site, repo_root):
	# frappe-dependent modules are imported here so the module still collects offline.
	from rheinwerk_mes.integration.migration.extractors import ofbiz
	from rheinwerk_mes.integration.migration.importer import import_extract

	extract = ofbiz.extract(repo_root / "tests/fixtures/legacy/ofbiz/plant-b-entities.xml")
	# The property asset is not a machine and never reaches the canonical extract.
	assert {record.key for record in extract.of("work_centre")} == {MACHINE}

	imported = import_extract(extract)
	assert MACHINE in imported
	assert site.db.exists("Workstation", MACHINE)
	assert not site.db.exists("Workstation", NON_MACHINE)


def test_tc_w0_006_migration_creates_no_asset_ledger_record(site, repo_root):
	from rheinwerk_mes.integration.migration.extractors import ofbiz
	from rheinwerk_mes.integration.migration.importer import import_extract

	import_extract(ofbiz.extract(repo_root / "tests/fixtures/legacy/ofbiz/plant-b-entities.xml"))

	# Asset accounting stays with the group ERP — no MES asset-ledger record is created.
	assert not site.get_all("Asset", filters={"asset_name": MACHINE}, pluck="name")
	assert not site.get_all("Asset", filters={"item_code": MACHINE}, pluck="name")

	# The OFBiz FixedAsset identifier is preserved out of the primary key (URS-W0-014).
	workstation = site.get_doc("Workstation", MACHINE)
	assert any(
		row.source_system == "OFBiz" and row.source_identifier == MACHINE for row in workstation.legacy_refs
	)
