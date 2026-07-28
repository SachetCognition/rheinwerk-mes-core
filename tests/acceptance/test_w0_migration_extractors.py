"""Master-data extractors for the three legacy sources (W0-5), offline.

TC-W0-009 step 1 (URS-W0-008) — Qcadoo extract record count = fixture source count.
TC-W0-010 step 1 (URS-W0-009) — ERPNext extract carries the `=`-mapped fields verbatim.
TC-W0-011 step 2 (URS-W0-010) — OFBiz CDM-08 machine rule and the exceptions report.
TC-W0-021 step 2 (URS-W0-018) — repeated extraction is byte-identical.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from rheinwerk_mes.integration.migration import extractors  # noqa: E402
from rheinwerk_mes.integration.migration.canonical import (  # noqa: E402
	CanonicalExtract,
	spot_check_sample,
)
from rheinwerk_mes.integration.migration.extractors.qcadoo import parse_dump  # noqa: E402


def extract(source: str) -> CanonicalExtract:
	return extractors.extract(source, REPO_ROOT / extractors.DEFAULT_FIXTURES[source])


def test_tc_w0_009_qcadoo_extract_matches_fixture_counts():
	"""TC-W0-009 step 1 (URS-W0-008 AC-1): the Qcadoo extract holds exactly the products,
	unit conversions, work centres, warehouses and technology headers of the Plant A dump."""
	fixture = REPO_ROOT / extractors.DEFAULT_FIXTURES["qcadoo"]
	tables = parse_dump(fixture.read_text(encoding="utf-8"))
	result = extract("qcadoo")

	assert result.counts() == {
		"item": len(tables["basic_product"]),
		"uom_conversion": len(tables["basic_unitconversionitem"]),
		"work_centre": len(tables["basic_workstation"]),
		# only `02warehouse` locations are warehouses; the production location is not carried
		"warehouse": sum(1 for row in tables["materialflow_location"] if row["type"] == "02warehouse"),
		"recipe_header": len(tables["technologies_technology"]),
	}


def test_tc_w0_009_qcadoo_preserves_conversion_and_legacy_number():
	"""TC-W0-009 step 2 (URS-W0-008 AC-2): 1 Sack = 25 kg survives the extract and the
	Qcadoo trigger-generated numbers stay as the legacy identifiers (URS-W0-014)."""
	result = extract("qcadoo")
	conversion = result.record("uom_conversion", "RW-CHM-0001|Sack")
	assert conversion is not None
	assert conversion.fields["conversion_factor"] == 25.0

	item = result.record("item", "RW-CHM-0001")
	assert item is not None
	assert item.source_identifier == "P-000123"
	assert item.fields["stock_uom"] == "Kg"

	technology = result.record("recipe_header", "000123/2025")
	assert technology is not None
	assert technology.fields["item_code"] == "RW-CHM-0003"


def test_tc_w0_010_erpnext_extract_is_verbatim():
	"""TC-W0-010 step 1+2 (URS-W0-009 AC-1): Plant C `=`-mapped fields are copied
	byte-identically out of the DocType export, including "FG Lager Süd"."""
	result = extract("erpnext")
	item = result.record("item", "RW-CHM-0002")
	assert item is not None
	assert item.fields == {
		"item_code": "RW-CHM-0002",
		"item_name": "Additiv K7",
		"item_group": "Raw Material",
		"stock_uom": "Kg",
		"description": "Additiv K7 für Rheinol-Compounds",
	}
	warehouse = result.record("warehouse", "FG Lager Süd")
	assert warehouse is not None
	assert warehouse.fields["disposal_method"] == "FIFO"
	assert set(result.direct_fields["item"]) >= {"item_code", "item_name", "stock_uom"}


def test_tc_w0_011_ofbiz_machine_assets_become_work_centres_only():
	"""TC-W0-011 step 1 (URS-W0-010 AC-1, CDM-08): only machine FixedAssets are carried,
	and no asset-accounting value (purchase cost, accounting class) enters the extract."""
	result = extract("ofbiz")
	work_centres = result.of("work_centre")
	assert [record.key for record in work_centres] == ["EXTRUDER-01"]
	assert set(work_centres[0].fields) == {"workstation_name", "production_line", "division"}
	assert result.record("item", "RW-CHM-0003") is not None


def test_tc_w0_011_ofbiz_unmappable_uom_is_reported():
	"""TC-W0-011 step 2 (URS-W0-010 AC-2): a Product whose UoM has no canonical equivalent
	lands in the exceptions report and is not imported with a defaulted UoM."""
	result = extract("ofbiz")
	reported = {exception.source_identifier: exception for exception in result.exceptions}
	assert "RHEINOL-40-LB" in reported
	assert reported["RHEINOL-40-LB"].reason == "unmappable_uom"
	assert result.record("item", "RW-CHM-0009") is None


def test_tc_w0_021_repeated_extraction_is_byte_identical():
	"""TC-W0-021 step 2 (URS-W0-018): extracting unchanged fixtures twice produces
	byte-identical canonical files for every source."""
	for source in extractors.SOURCES:
		first = extract(source).to_json()
		second = extract(source).to_json()
		assert first == second, f"{source}: extraction is not deterministic"
		assert CanonicalExtract.from_json(first).to_json() == first


def test_spot_check_sample_is_deterministic_and_meets_the_five_percent_floor():
	"""TC-W0-012 (URS-W0-011): the reconciliation sample is the documented deterministic
	5 % sample with a minimum of 10 records (`docs/urs/URS-W0-foundation.md` §5)."""
	keys = [f"RW-CHM-{index:04d}" for index in range(1, 401)]
	sample = spot_check_sample(keys)
	assert sample == spot_check_sample(list(reversed(keys)))
	assert len(sample) == 20
	assert len(spot_check_sample(keys[:50])) == 10
	assert len(spot_check_sample(keys[:4])) == 4
