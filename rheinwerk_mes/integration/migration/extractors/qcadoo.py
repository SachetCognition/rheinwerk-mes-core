"""Plant A (Qcadoo) master-data extractor — URS-W0-008.

Reads a `pg_dump` subset of the Qcadoo PostgreSQL schema (`COPY … FROM stdin` blocks)
without a PostgreSQL server, so the extract is reproducible in CI from the committed
fixture. Behaviour is re-expressed from the Qcadoo *model definitions* — no Java is
ported: `mes-plugins-basic/.../model/product.xml` (product, unit),
`.../model/unitConversionItem.xml` (unit conversions), `.../model/division.xml` and
`.../model/workstation.xml` (work centre), `mes-plugins-technologies/.../model/
technology.xml` (technology headers).

Transforms (CDM legend, `docs/canonical-model/README.md`):

* `item_code` ≈ `basic_product.additionalcode` (group article code) falling back to
  `basic_product.number`; the Qcadoo `number` is always preserved as the legacy identifier.
* `stock_uom` ≈ `basic_product.unit`, title-cased to the substrate UoM names (`kg` → `Kg`).
* `work_centre` ≈ `basic_workstation` + `basic_productionline` + `basic_division` (CDM-08).
* `warehouse` ≈ `materialflow_location` rows of type `02warehouse`; other location types
  are not warehouses and are deliberately not carried (`✕`).
* `recipe_header` ≈ `technologies_technology` header (governance state lands in W1, CDM-04).

Unmappable units are reported, never defaulted (same rule as URS-W0-010 AC-2).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rheinwerk_mes.integration.migration.canonical import (
	CanonicalExtract,
	CanonicalRecord,
	MigrationException,
)

DEFAULT_FIXTURE = "tests/fixtures/legacy/qcadoo/plant-a.sql"

COPY_HEADER = re.compile(r"^COPY\s+(?:public\.)?(?P<table>\w+)\s*\((?P<columns>[^)]*)\)\s+FROM stdin;\s*$")

#: Qcadoo lower-case unit symbols → substrate UoM names. A unit outside this table is an
#: exception (URS-W0-010 AC-2 rule, applied to every source).
UOM_MAP = {
	"kg": "Kg",
	"sack": "Sack",
	"pail": "Pail",
	"l": "Litre",
	"pcs": "Nos",
}

WAREHOUSE_LOCATION_TYPE = "02warehouse"

DIRECT_FIELDS = {
	"item": ("item_name",),
	"uom_conversion": ("conversion_factor", "item_code", "uom"),
	"work_centre": ("workstation_name",),
	"warehouse": ("warehouse_name",),
	"recipe_header": ("item_code", "recipe_code"),
}


def parse_dump(text: str) -> dict[str, list[dict[str, str | None]]]:
	"""Parse the `COPY … FROM stdin` blocks of a `pg_dump` into table → rows."""
	tables: dict[str, list[dict[str, str | None]]] = {}
	columns: list[str] = []
	table: str | None = None
	for line in text.splitlines():
		if table is None:
			header = COPY_HEADER.match(line.strip())
			if header:
				table = header.group("table")
				columns = [column.strip() for column in header.group("columns").split(",")]
				tables.setdefault(table, [])
			continue
		if line.strip() == "\\.":
			table = None
			continue
		values: list[str | None] = [None if value == "\\N" else value for value in line.split("\t")]
		if len(values) != len(columns):
			raise ValueError(f"{table}: expected {len(columns)} columns, got {len(values)} in {line!r}")
		tables[table].append(dict(zip(columns, values, strict=True)))
	return tables


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
	return {row["id"]: row for row in rows}


def _uom(symbol: str | None) -> str | None:
	if not symbol:
		return None
	return UOM_MAP.get(symbol.strip().lower())


def extract(path: str | Path) -> CanonicalExtract:
	"""Extract Plant A master data from the Qcadoo dump at `path`."""
	tables = parse_dump(Path(path).read_text(encoding="utf-8"))
	records: list[CanonicalRecord] = []
	exceptions: list[MigrationException] = []

	products = tables.get("basic_product", [])
	divisions = _by_id(tables.get("basic_division", []))
	lines = _by_id(tables.get("basic_productionline", []))
	item_code_by_product_id: dict[str, str] = {}

	for product in products:
		item_code = product.get("additionalcode") or product["number"]
		stock_uom = _uom(product.get("unit"))
		if stock_uom is None:
			exceptions.append(
				MigrationException(
					entity="item",
					source_identifier=product["number"],
					reason="unmappable_uom",
					detail=f"Qcadoo unit {product.get('unit')!r} has no canonical UoM equivalent",
				)
			)
			continue
		item_code_by_product_id[product["id"]] = item_code
		records.append(
			CanonicalRecord(
				entity="item",
				key=item_code,
				fields={
					"item_code": item_code,
					"item_name": product["name"],
					"stock_uom": stock_uom,
					"item_group": "Products"
					if product.get("globaltypeofmaterial") == "03finalProduct"
					else "Raw Material",
					"description": product["name"],
				},
				source_entity="basic_product",
				source_identifier=product["number"],
			)
		)

	for conversion in tables.get("basic_unitconversionitem", []):
		item_code = item_code_by_product_id.get(conversion["product_id"])
		if item_code is None:
			continue
		pack_uom = _uom(conversion.get("unitfrom"))
		if pack_uom is None:
			exceptions.append(
				MigrationException(
					entity="uom_conversion",
					source_identifier=f"{item_code}|{conversion.get('unitfrom')}",
					reason="unmappable_uom",
					detail=f"Qcadoo unit {conversion.get('unitfrom')!r} has no canonical UoM equivalent",
				)
			)
			continue
		factor = float(conversion["quantityto"]) / float(conversion["quantityfrom"])
		records.append(
			CanonicalRecord(
				entity="uom_conversion",
				key=f"{item_code}|{pack_uom}",
				fields={
					"item_code": item_code,
					"uom": pack_uom,
					"conversion_factor": factor,
				},
				source_entity="basic_unitconversionitem",
				source_identifier=conversion["id"],
			)
		)

	for workstation in tables.get("basic_workstation", []):
		line = lines.get(workstation.get("productionline_id") or "")
		division = divisions.get(workstation.get("division_id") or "")
		records.append(
			CanonicalRecord(
				entity="work_centre",
				key=workstation["number"],
				fields={
					"workstation_name": workstation["number"],
					"production_line": line["number"] if line else None,
					"division": division["name"] if division else None,
				},
				source_entity="basic_workstation",
				source_identifier=workstation["number"],
			)
		)

	for location in tables.get("materialflow_location", []):
		if location.get("type") != WAREHOUSE_LOCATION_TYPE:
			continue
		records.append(
			CanonicalRecord(
				entity="warehouse",
				key=location["name"],
				fields={"warehouse_name": location["name"], "disposal_method": None},
				source_entity="materialflow_location",
				source_identifier=location["number"],
			)
		)

	for technology in tables.get("technologies_technology", []):
		item_code = item_code_by_product_id.get(technology["product_id"])
		if item_code is None:
			continue
		records.append(
			CanonicalRecord(
				entity="recipe_header",
				key=technology["number"],
				fields={
					"recipe_code": technology["number"],
					"item_code": item_code,
					"recipe_name": technology["name"],
					"source_state": technology.get("state"),
				},
				source_entity="technologies_technology",
				source_identifier=technology["number"],
			)
		)

	return CanonicalExtract(
		source="qcadoo",
		records=tuple(records),
		exceptions=tuple(exceptions),
		direct_fields=DIRECT_FIELDS,
	)
