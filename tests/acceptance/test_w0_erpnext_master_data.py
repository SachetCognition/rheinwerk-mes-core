"""Plant C (ERPNext) master-data extractor — TC-W0-010 (URS-W0-009).

Step 1 runs offline: the extractor copies the `=`-mapped fields out of the DocType export
verbatim. Step 2 needs the substrate: extract → import → re-export must show zero
differences on those fields for item RW-CHM-0002 and warehouse "FG Lager Süd".
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
	checksum,
)

MIGRATION = "rheinwerk_mes.integration.migration"


def plant_c() -> CanonicalExtract:
	return extractors.extract("erpnext", REPO_ROOT / extractors.DEFAULT_FIXTURES["erpnext"])


def test_tc_w0_010_extract_carries_the_direct_mapped_fields_verbatim():
	"""TC-W0-010 step 1 (URS-W0-009 AC-1): item RW-CHM-0002 and warehouse "FG Lager Süd"
	leave the Plant C export with their `=`-mapped values unchanged."""
	extract = plant_c()

	item = extract.record("item", "RW-CHM-0002")
	assert item is not None
	assert item.fields == {
		"item_code": "RW-CHM-0002",
		"item_name": "Additiv K7",
		"item_group": "Raw Material",
		"stock_uom": "Kg",
		"description": "Additiv K7 für Rheinol-Compounds",
	}

	warehouse = extract.record("warehouse", "FG Lager Süd")
	assert warehouse is not None
	assert warehouse.fields == {"warehouse_name": "FG Lager Süd", "disposal_method": "FIFO"}

	assert set(extract.direct_fields["item"]) >= {"item_code", "item_name", "stock_uom"}


def test_extract_covers_every_doctype_of_the_plant_c_export():
	"""URS-W0-009: Item, UOM Conversion, Workstation, BOM header and Warehouse are all
	carried — the BOM header as an extract-only `recipe_header` (imported in W1)."""
	extract = plant_c()

	assert extract.counts() == {
		"item": 2,
		"uom_conversion": 1,
		"work_centre": 1,
		"warehouse": 1,
		"recipe_header": 1,
	}
	assert extract.record("uom_conversion", "RW-CHM-0002|Pail").fields["conversion_factor"] == 5.0
	assert extract.record("work_centre", "PACK-01").fields["division"] == "Abfüllung"
	assert extract.record("recipe_header", "BOM-RW-CHM-0003-C01").fields["item_code"] == "RW-CHM-0003"
	assert extract.source_system == "ERPNext Legacy"


def test_source_identifiers_are_preserved_unchanged():
	"""URS-W0-009: the anchor model is identical, so the Plant C keys are the target keys —
	no re-numbering (URS-W0-014)."""
	extract = plant_c()

	for record in extract.records:
		assert record.source_identifier == record.key


def test_repeated_extraction_is_byte_identical():
	"""URS-W0-018: extracting the unchanged fixture twice yields byte-identical output, and
	the canonical file round-trips through its own serialisation."""
	first = plant_c().to_json()
	assert first == plant_c().to_json()
	assert CanonicalExtract.from_json(first).to_json() == first


def test_tc_w0_010_direct_mapped_fields_are_byte_identical_after_import(site):
	"""TC-W0-010 step 2 (URS-W0-009 AC-1): after the import, re-exporting the target
	reproduces every `=`-mapped value — zero differences, checksums equal."""
	extract = plant_c()
	result = site.get_attr(f"{MIGRATION}.importer.import_extract")(extract)
	reexported = site.get_attr(f"{MIGRATION}.exporter.reexport")(extract)

	assert result.imported == {"item": 2, "uom_conversion": 1, "work_centre": 1, "warehouse": 1}
	assert result.deferred == {"recipe_header": 1}

	for entity, direct in extract.direct_fields.items():
		if entity not in result.imported:
			continue
		assert [record.key for record in reexported.of(entity)] == [
			record.key for record in extract.of(entity)
		], entity
		for record in extract.of(entity):
			target = reexported.record(entity, record.key)
			for name in direct:
				assert record.fields[name] == target.fields[name], f"{entity} {record.key}.{name}"
		assert checksum(extract, entity) == checksum(reexported, entity), entity

	assert site.db.exists("Item", "RW-CHM-0002")
	assert site.db.exists("Warehouse", {"warehouse_name": "FG Lager Süd"})
