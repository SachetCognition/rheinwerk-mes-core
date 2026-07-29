"""Plant C (ERPNext) master-data extractor — URS-W0-009.

The Plant C instance runs the same anchor model as the target substrate, so every field
below is a CDM `=` (direct) mapping: values are copied verbatim, never normalised, and the
re-export of the target is checksummed against them for byte-identity (TC-W0-010).

Input is a `bench export-doc`-style DocType export: `{"docs": [{"doctype": …}, …]}`
covering Item (with `uoms`), Warehouse, Workstation and BOM headers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord

DEFAULT_FIXTURE = "tests/fixtures/legacy/erpnext/plant-c.json"

ITEM_FIELDS = ("item_code", "item_name", "item_group", "stock_uom", "description")

DIRECT_FIELDS = {
	"item": ITEM_FIELDS,
	"uom_conversion": ("conversion_factor", "item_code", "uom"),
	"work_centre": ("workstation_name", "production_line", "division"),
	"warehouse": ("warehouse_name", "disposal_method"),
	"recipe_header": ("item_code", "quantity", "recipe_code", "uom"),
}


def extract(path: str | Path) -> CanonicalExtract:
	"""Extract Plant C master data from the ERPNext DocType export at `path`."""
	payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
	records: list[CanonicalRecord] = []

	for doc in payload.get("docs", []):
		doctype = doc.get("doctype")
		if doctype == "Item":
			item_code = doc["item_code"]
			records.append(
				CanonicalRecord(
					entity="item",
					key=item_code,
					fields={name: doc.get(name) for name in ITEM_FIELDS},
					source_entity="Item",
					source_identifier=item_code,
				)
			)
			for row in doc.get("uoms", []):
				records.append(
					CanonicalRecord(
						entity="uom_conversion",
						key=f"{item_code}|{row['uom']}",
						fields={
							"item_code": item_code,
							"uom": row["uom"],
							"conversion_factor": float(row["conversion_factor"]),
						},
						source_entity="UOM Conversion Detail",
						source_identifier=f"{item_code}|{row['uom']}",
					)
				)
		elif doctype == "Warehouse":
			records.append(
				CanonicalRecord(
					entity="warehouse",
					key=doc["warehouse_name"],
					fields={
						"warehouse_name": doc["warehouse_name"],
						"disposal_method": doc.get("disposal_method"),
					},
					source_entity="Warehouse",
					source_identifier=doc["warehouse_name"],
				)
			)
		elif doctype == "Workstation":
			records.append(
				CanonicalRecord(
					entity="work_centre",
					key=doc["workstation_name"],
					fields={
						"workstation_name": doc["workstation_name"],
						"production_line": doc.get("production_line"),
						"division": doc.get("division"),
					},
					source_entity="Workstation",
					source_identifier=doc["workstation_name"],
				)
			)
		elif doctype == "BOM":
			records.append(
				CanonicalRecord(
					entity="recipe_header",
					key=doc["name"],
					fields={
						"recipe_code": doc["name"],
						"item_code": doc["item"],
						"quantity": float(doc.get("quantity", 0)),
						"uom": doc.get("uom"),
						"source_state": "Aktiv" if doc.get("is_active") else "Inaktiv",
					},
					source_entity="BOM",
					source_identifier=doc["name"],
				)
			)

	return CanonicalExtract(source="erpnext", records=tuple(records), direct_fields=DIRECT_FIELDS)
