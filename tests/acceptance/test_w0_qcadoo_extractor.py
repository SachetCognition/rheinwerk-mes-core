"""Qcadoo (Plant A) master-data extractor — TC-W0-009 (URS-W0-008), offline.

Step 1 (AC-1) — the canonical import file is produced and its record count equals the
fixture source count. Step 2 (AC-2) — RW-CHM-0001 carries the 1 Sack = 25 kg conversion
and the Qcadoo product number that the importer records in the legacy mapping.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from rheinwerk_mes.integration.migration import extractors  # noqa: E402
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract  # noqa: E402
from rheinwerk_mes.integration.migration.extract import write_extract  # noqa: E402
from rheinwerk_mes.integration.migration.extractors.qcadoo import parse_dump  # noqa: E402

FIXTURE = REPO_ROOT / extractors.DEFAULT_FIXTURES["qcadoo"]


@pytest.fixture(scope="module")
def tables() -> dict[str, list[dict[str, str | None]]]:
	return parse_dump(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def extract() -> CanonicalExtract:
	return extractors.extract("qcadoo", FIXTURE)


def test_tc_w0_009_extract_record_count_equals_fixture_source_count(extract, tables):
	"""TC-W0-009 step 1 (AC-1): every product, unit conversion, workstation, warehouse
	location and technology header of the Plant A dump is carried, and nothing else."""
	assert extract.counts() == {
		"item": len(tables["basic_product"]),
		"uom_conversion": len(tables["basic_unitconversionitem"]),
		"work_centre": len(tables["basic_workstation"]),
		# only `02warehouse` locations are warehouses; the production location is not carried
		"warehouse": sum(1 for row in tables["materialflow_location"] if row["type"] == "02warehouse"),
		"recipe_header": len(tables["technologies_technology"]),
	}
	assert extract.exceptions == ()


def test_tc_w0_009_canonical_import_file_is_produced(tmp_path, extract):
	"""TC-W0-009 step 1 (AC-1): the extractor run writes a canonical import file that
	round-trips through the format without loss."""
	output = tmp_path / "plant-a.canonical.json"
	written = write_extract("qcadoo", output, FIXTURE)

	assert written.as_dict() == extract.as_dict()
	reloaded = CanonicalExtract.from_json(output.read_text(encoding="utf-8"))
	assert reloaded.counts() == extract.counts()
	assert reloaded.source_system == "Qcadoo"


def test_tc_w0_009_conversion_and_qcadoo_number_survive_the_extract(extract):
	"""TC-W0-009 step 2 (AC-2): 1 Sack = 25 kg is intact on RW-CHM-0001 and the Qcadoo
	product number reaches the importer as the legacy identifier (URS-W0-014)."""
	item = extract.record("item", "RW-CHM-0001")
	assert item is not None
	assert item.fields["stock_uom"] == "Kg"
	assert item.source_entity == "basic_product"
	assert item.source_identifier == "P-000123"

	conversion = extract.record("uom_conversion", "RW-CHM-0001|Sack")
	assert conversion is not None
	assert conversion.fields == {
		"item_code": "RW-CHM-0001",
		"uom": "Sack",
		"conversion_factor": 25.0,
	}


def test_qcadoo_work_centre_carries_production_line_and_division(extract):
	"""CDM-08: a Qcadoo workstation resolves its production line and division names."""
	work_centre = extract.record("work_centre", "MIX-02")
	assert work_centre is not None
	assert work_centre.fields == {
		"workstation_name": "MIX-02",
		"production_line": "LINE-1",
		"division": "Mischerei",
	}


def test_qcadoo_technology_header_links_its_product(extract):
	"""CDM-04: the technology header is carried with the canonical item it produces."""
	technology = extract.record("recipe_header", "000123/2025")
	assert technology is not None
	assert technology.fields["item_code"] == "RW-CHM-0003"
	assert technology.fields["source_state"] == "05accepted"


def test_qcadoo_unmappable_unit_is_reported_never_defaulted(tmp_path):
	"""A unit outside the canonical UoM table lands in the exceptions report and the
	product is not carried with a defaulted UoM."""
	dump = FIXTURE.read_text(encoding="utf-8").replace(
		"3\tP-000125\tRheinol 40 Compound\tkg\tRW-CHM-0003\t03finalProduct",
		"3\tP-000125\tRheinol 40 Compound\tlb\tRW-CHM-0003\t03finalProduct",
	)
	fixture = tmp_path / "plant-a-unmappable.sql"
	fixture.write_text(dump, encoding="utf-8")

	result = extractors.extract("qcadoo", fixture)

	assert result.record("item", "RW-CHM-0003") is None
	reported = {exception.source_identifier: exception for exception in result.exceptions}
	assert reported["P-000125"].reason == "unmappable_uom"


def test_tc_w0_021_repeated_extraction_is_byte_identical():
	"""TC-W0-021 step 2 (URS-W0-018): extracting the unchanged fixture twice produces
	byte-identical canonical files."""
	first = extractors.extract("qcadoo", FIXTURE).to_json()
	second = extractors.extract("qcadoo", FIXTURE).to_json()
	assert first == second
	assert CanonicalExtract.from_json(first).to_json() == first


def test_unknown_source_is_rejected():
	with pytest.raises(ValueError, match="unknown migration source"):
		extractors.extract("sap", FIXTURE)
