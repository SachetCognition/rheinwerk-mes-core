"""Master-data round trip on the substrate: extract → import → re-export → reconcile.

TC-W0-009 step 2 (URS-W0-008 AC-2) — Qcadoo import keeps the conversion and legacy number.
TC-W0-010 step 2 (URS-W0-009 AC-1) — Plant C `=`-mapped fields byte-identical after import.
TC-W0-011 step 1 (URS-W0-010 AC-1) — OFBiz machine FixedAsset imports as a Workstation only.
TC-W0-012 (URS-W0-011 AC-1/AC-2) — three PASS reports; a mutated record yields a named FAIL.
TC-W0-013 (URS-W0-011 AC-3) — rollback removes exactly that run's imports; re-run passes.
TC-W0-021 step 1 (URS-W0-018) — each source's round trip stays far below the 30-minute budget.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from rheinwerk_mes.integration.migration import extractors  # noqa: E402

MIGRATION = "rheinwerk_mes.integration.migration"
ROUND_TRIP_BUDGET_SECONDS = 30 * 60


def api(site, dotted: str):
	return site.get_attr(f"{MIGRATION}.{dotted}")


def run(site, source: str, *, keep_on_fail: bool = False):
	return api(site, "cli.round_trip")(source, keep_on_fail=keep_on_fail)


def import_source(site, source: str):
	"""Extract and import one source, returning (extract, import result)."""
	extract = api(site, "cli.extract_source")(source)
	return extract, api(site, "importer.import_extract")(extract)


def test_tc_w0_012_all_three_sources_reconcile_pass(site):
	"""TC-W0-012 step 1 (URS-W0-011 AC-1): every source round-trips with source =
	imported = re-exported counts for items, work centres and warehouses, status PASS."""
	for source in extractors.SOURCES:
		report = run(site, source)
		assert report.status == "PASS", report.to_markdown()
		for entity in report.entities:
			assert entity.source_count == entity.imported_count == entity.reexported_count
			assert entity.source_checksum == entity.reexported_checksum
		assert {entity.entity for entity in report.entities} >= {"item", "work_centre", "warehouse"}


def test_tc_w0_009_qcadoo_import_keeps_conversion_and_legacy_number(site):
	"""TC-W0-009 step 2 (URS-W0-008 AC-2): after import RW-CHM-0001 carries 1 Sack = 25 kg
	and its Qcadoo product number in `legacy_refs`."""
	assert run(site, "qcadoo").status == "PASS"
	item = site.get_doc("Item", "RW-CHM-0001")
	assert {row.uom: row.conversion_factor for row in item.uoms}["Sack"] == 25.0
	qcadoo_refs = {row.source_identifier for row in item.legacy_refs if row.source_system == "Qcadoo"}
	assert "P-000123" in qcadoo_refs


def test_tc_w0_010_erpnext_direct_mapped_fields_are_byte_identical(site):
	"""TC-W0-010 step 2 (URS-W0-009 AC-1): zero differences on the `=`-mapped fields of the
	Plant C export — item RW-CHM-0002 and warehouse "FG Lager Süd" included."""
	extract, result = import_source(site, "erpnext")
	reexported = api(site, "exporter.reexport")(extract)
	for entity, direct in extract.direct_fields.items():
		for record in extract.of(entity):
			target = reexported.record(entity, record.key)
			if target is None:
				continue
			for name in direct:
				if name in record.fields and name in target.fields:
					assert record.fields[name] == target.fields[name], f"{entity} {record.key}.{name}"
	assert result.imported["warehouse"] == 1
	assert site.db.exists("Warehouse", {"warehouse_name": "FG Lager Süd"})


def test_tc_w0_011_ofbiz_machine_asset_becomes_workstation_without_asset_record(site):
	"""TC-W0-011 step 1+2 (URS-W0-010, CDM-08): the machine FixedAsset lands as exactly one
	Workstation, no Asset (accounting) record is created, and the unmappable-UoM product is
	reported as an exception instead of being imported."""
	report = run(site, "ofbiz")
	assert report.status == "PASS", report.to_markdown()
	assert site.db.exists("Workstation", "EXTRUDER-01")
	assert not site.db.exists("Asset", {"asset_name": "Extruder 01"})
	assert not site.db.exists("Workstation", "BUERO-NORD")
	assert not site.db.exists("Item", "RW-CHM-0009")
	assert [exception["source_identifier"] for exception in report.exceptions] == ["RHEINOL-40-LB"]
	assert "RHEINOL-40-LB" in report.to_markdown()


def test_tc_w0_012_mutated_record_yields_a_named_fail(site):
	"""TC-W0-012 step 2 (URS-W0-011 AC-2): renaming one imported item makes the
	reconciliation FAIL and name the mismatched record."""
	extract, result = import_source(site, "erpnext")
	item = site.get_doc("Item", "RW-CHM-0002")
	item.item_name = "Additiv K7 (manuell umbenannt)"
	item.save(ignore_permissions=True)

	report = api(site, "reconcile.reconcile")(
		extract,
		api(site, "exporter.reexport")(extract),
		run_id=result.run_id,
		imported=result.imported,
	)
	assert report.status == "FAIL"
	named = [difference for difference in report.differences if difference.key == "RW-CHM-0002"]
	assert named, report.to_markdown()
	assert any(difference.kind == "field" for difference in named)
	assert "RW-CHM-0002" in report.to_markdown()


def test_tc_w0_013_rollback_removes_exactly_this_runs_imports(site):
	"""TC-W0-013 (URS-W0-011 AC-3): rolling a run back deletes the documents it inserted,
	restores the ones it updated, and a clean re-run reconciles PASS again."""
	before_description = site.db.get_value("Item", "RW-CHM-0001", "description")
	extract, result = import_source(site, "ofbiz")
	assert site.db.exists("Workstation", "EXTRUDER-01")

	outcome = api(site, "rollback.rollback_result")(result)

	assert outcome["deleted"] >= 1
	assert not site.db.exists("Workstation", "EXTRUDER-01")
	assert site.db.get_value("Item", "RW-CHM-0001", "description") == before_description
	# untouched records survive the rollback
	assert site.db.exists("Item", "RW-CHM-0002")

	assert run(site, "ofbiz").status == "PASS"


def test_tc_w0_013_rollback_from_journal_file(site):
	"""TC-W0-013 (URS-W0-011 AC-3): the run journal is persisted, so a failed run can be
	reversed by run id after the process that imported it has gone."""
	_, result = import_source(site, "qcadoo")
	journal = api(site, "importer.read_journal")(result.run_id)
	assert [entry.name for entry in journal.journal] == [entry.name for entry in result.journal]
	api(site, "rollback.rollback_run")(result.run_id)
	assert not site.db.exists("Workstation", "MIX-02")


def test_tc_w0_021_round_trip_stays_within_the_ci_budget(site):
	"""TC-W0-021 step 1 (URS-W0-018): each source's full round trip completes well inside
	the 30-minute CI budget."""
	for source in extractors.SOURCES:
		started = time.monotonic()
		report = run(site, source)
		elapsed = time.monotonic() - started
		assert report.status == "PASS"
		assert elapsed < ROUND_TRIP_BUDGET_SECONDS, f"{source}: {elapsed:.1f}s"
		assert report.duration_seconds < ROUND_TRIP_BUDGET_SECONDS
