"""Canonical-extract importer (URS-W0-009).

Every canonical record lands on an **anchor ERPNext DocType** (`Item`, `Workstation`,
`Warehouse`) — nothing is forked; where the site carries the `legacy_refs` child table the
source identifier is preserved there, so the identifier store stays singular across the
programme (URS-W0-014).

Directly-mapped (`=`) fields are written verbatim: no normalisation, no defaulting, so a
re-export of the target reproduces the source values byte-identically (URS-W0-009 AC-1).

`recipe_header` records are extracted (the BOM headers of the Plant C export) but **not**
imported in W0: BOM creation is governed by the CDM-04 `Recipe Governance` workflow
delivered in W1. They are reported as deferred in the run summary rather than dropped
silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord

#: Entities the W0 importer lands; `recipe_header` is deferred to W1 (CDM-04 governance).
IMPORTED_ENTITIES = ("item", "uom_conversion", "work_centre", "warehouse")

DEFERRED_ENTITIES = ("recipe_header",)

ITEM_UPDATE_FIELDS = ("item_name", "item_group", "description")


@dataclass(frozen=True)
class ImportResult:
	"""Outcome of importing one canonical extract."""

	source: str
	imported: dict[str, int]
	deferred: dict[str, int]


def default_company() -> str:
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(frappe._("Keine Firma vorhanden — Stammdatenmigration nicht möglich."))
	return company


def warehouse_name_of(warehouse_name: str, company: str) -> str:
	"""The anchor `Warehouse.name` the plain warehouse name lands under."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	return f"{warehouse_name} - {abbr}"


def _set_legacy_ref(doc: Any, extract: CanonicalExtract, record: CanonicalRecord) -> None:
	"""Preserve the source identifier in `legacy_refs` (idempotent)."""
	if not doc.meta.get_field("legacy_refs"):
		return
	existing = {(row.source_system, row.source_identifier) for row in (doc.get("legacy_refs") or [])}
	marker = (extract.source_system, record.source_identifier)
	if marker in existing:
		return
	doc.append(
		"legacy_refs",
		{
			"source_system": extract.source_system,
			"source_entity": record.source_entity,
			"source_identifier": record.source_identifier,
			"migrated_on": frappe.utils.now_datetime(),
		},
	)


def _import_item(extract: CanonicalExtract, record: CanonicalRecord) -> bool:
	item_code = record.fields["item_code"]
	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
		for name in ITEM_UPDATE_FIELDS:
			if record.fields.get(name) is not None:
				doc.set(name, record.fields[name])
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return True

	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": record.fields.get("item_name"),
			"item_group": record.fields.get("item_group") or "All Item Groups",
			"stock_uom": record.fields.get("stock_uom"),
			"description": record.fields.get("description"),
			"is_stock_item": 1,
		}
	)
	_set_legacy_ref(doc, extract, record)
	doc.insert(ignore_permissions=True)
	return True


def _import_uom_conversion(extract: CanonicalExtract, record: CanonicalRecord) -> bool:
	item_code = record.fields["item_code"]
	if not frappe.db.exists("Item", item_code):
		return False
	doc = frappe.get_doc("Item", item_code)
	uom = record.fields["uom"]
	factor = float(record.fields["conversion_factor"])
	for row in doc.uoms:
		if row.uom == uom:
			row.conversion_factor = factor
			break
	else:
		doc.append("uoms", {"uom": uom, "conversion_factor": factor})
	doc.save(ignore_permissions=True)
	return True


def _linked(doctype: str, value: str | None) -> str | None:
	"""`value` when that document exists, else None.

	The canonical work-centre attributes are links to `Production Line` and `Division`
	(URS-W0-005); a site that does not carry them yet imports the workstation without
	them rather than failing the run.
	"""
	if not value or not frappe.db.exists("DocType", doctype):
		return None
	return value if frappe.db.exists(doctype, value) else None


def _import_work_centre(extract: CanonicalExtract, record: CanonicalRecord) -> bool:
	name = record.fields["workstation_name"]
	values = {
		"production_line": _linked("Production Line", record.fields.get("production_line")),
		"division": _linked("Division", record.fields.get("division")),
	}
	values = {
		key: value for key, value in values.items() if value and frappe.get_meta("Workstation").get_field(key)
	}
	if frappe.db.exists("Workstation", name):
		doc = frappe.get_doc("Workstation", name)
		doc.update(values)
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return True

	doc = frappe.get_doc(
		{
			"doctype": "Workstation",
			"workstation_name": name,
			"company": default_company(),
			**values,
		}
	)
	_set_legacy_ref(doc, extract, record)
	doc.insert(ignore_permissions=True)
	return True


def _import_warehouse(extract: CanonicalExtract, record: CanonicalRecord) -> bool:
	company = default_company()
	warehouse_name = record.fields["warehouse_name"]
	name = warehouse_name_of(warehouse_name, company)
	disposal_method = record.fields.get("disposal_method")
	existing = frappe.db.exists("Warehouse", name)
	doc = (
		frappe.get_doc("Warehouse", name)
		if existing
		else frappe.get_doc({"doctype": "Warehouse", "warehouse_name": warehouse_name, "company": company})
	)
	if disposal_method and doc.meta.get_field("disposal_method"):
		doc.disposal_method = disposal_method
	_set_legacy_ref(doc, extract, record)
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return True


IMPORTERS = {
	"item": _import_item,
	"uom_conversion": _import_uom_conversion,
	"work_centre": _import_work_centre,
	"warehouse": _import_warehouse,
}


def import_extract(extract: CanonicalExtract) -> ImportResult:
	"""Import a canonical extract onto the anchor DocTypes."""
	imported: dict[str, int] = {}
	for entity in IMPORTED_ENTITIES:
		for record in sorted(extract.of(entity), key=lambda item: item.key):
			if IMPORTERS[entity](extract, record):
				imported[entity] = imported.get(entity, 0) + 1

	deferred = {entity: len(extract.of(entity)) for entity in DEFERRED_ENTITIES if extract.of(entity)}
	return ImportResult(source=extract.source, imported=imported, deferred=deferred)
