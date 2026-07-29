"""Plant B (OFBiz) master-data extraction, offline — URS-W0-010.

TC-W0-011 step 1 — CDM-08: only machine FixedAssets are carried, as work centres, and no
asset-accounting value enters the extract.
TC-W0-011 step 2 — a Product whose unit of measure has no canonical equivalent lands in the
exceptions report instead of being defaulted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rheinwerk_mes.integration.migration import exceptions_report, extractors
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

FIXTURE = Path(extractors.DEFAULT_FIXTURES["ofbiz"])


def ofbiz_extract(repo_root: Path) -> CanonicalExtract:
	return extractors.extract("ofbiz", repo_root / FIXTURE)


def test_tc_w0_011_machine_fixed_asset_becomes_exactly_one_work_centre(repo_root):
	"""TC-W0-011 step 1 (AC-1, CDM-08): the single machine FixedAsset yields exactly one
	work centre; the PROPERTY asset is not carried at all."""
	work_centres = ofbiz_extract(repo_root).of("work_centre")

	assert [record.key for record in work_centres] == ["Extruder 01"]
	assert work_centres[0].source_entity == "FixedAsset"
	assert work_centres[0].source_identifier == "EXTRUDER-01"


def test_tc_w0_011_no_asset_accounting_value_is_carried(repo_root):
	"""TC-W0-011 step 1 (AC-1, ADR-010): asset accounting stays with the group ERP — the
	extract carries no purchase cost, accounting class or depreciation, anywhere."""
	extract = ofbiz_extract(repo_root)

	assert set(extract.of("work_centre")[0].fields) == {"workstation_name"}
	accounting = {"purchase_cost", "purchaseCost", "class_enum_id", "classEnumId", "depreciation"}
	for record in extract.records:
		assert not accounting & set(record.fields)


def test_tc_w0_011_product_and_facility_master_data_is_extracted(repo_root):
	"""TC-W0-011 step 1 (AC-1): the Product mapping to RW-CHM-0003 is extracted under its
	SKU with its OFBiz product id preserved, and only WAREHOUSE facilities are warehouses."""
	extract = ofbiz_extract(repo_root)

	item = extract.record("item", "RW-CHM-0003")
	assert item is not None
	assert item.source_identifier == "RHEINOL-40-CMPD"
	assert item.fields["stock_uom"] == "Kg"
	assert item.fields["item_group"] == "Products"
	assert [record.key for record in extract.of("warehouse")] == ["Lager West"]


def test_tc_w0_011_unmappable_uom_is_reported_and_not_defaulted(repo_root):
	"""TC-W0-011 step 2 (AC-2): the Product with quantityUomId "WT_lb" is absent from the
	records and present in the exceptions report, naming its reason."""
	extract = ofbiz_extract(repo_root)

	assert extract.record("item", "RW-CHM-0009") is None
	reported = {exception.source_identifier: exception for exception in extract.exceptions}
	assert set(reported) == {"RHEINOL-40-LB"}
	assert reported["RHEINOL-40-LB"].reason == "unmappable_uom"
	assert "WT_lb" in reported["RHEINOL-40-LB"].detail

	report = exceptions_report.to_markdown(extract)
	assert "RHEINOL-40-LB" in report
	assert "Mengeneinheit ohne kanonische Entsprechung" in report


def test_repeated_extraction_is_byte_identical(repo_root):
	"""Re-extracting an unchanged export produces an identical canonical file, so a
	migration run can be diffed against its predecessor."""
	first = ofbiz_extract(repo_root).to_json()

	assert ofbiz_extract(repo_root).to_json() == first
	assert CanonicalExtract.from_json(first).to_json() == first


def test_unknown_source_is_rejected():
	"""The extractor registry refuses a source it has no extractor for."""
	with pytest.raises(ValueError, match="plant-x"):
		extractors.extract("plant-x", FIXTURE)
