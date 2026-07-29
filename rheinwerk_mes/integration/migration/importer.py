"""Canonical-extract importer (W0-5).

Every canonical record lands on an **anchor ERPNext DocType** — `Item`, `Workstation`,
`Warehouse` — and nothing is forked. The import is idempotent: a record whose target
already exists is updated in place, so re-running a migration never duplicates master data.

The source identifier is preserved in the `legacy_refs` child table when the substrate
carries it (URS-W0-014); on a site without that Custom Field the import still succeeds and
the identifier is simply not stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord

#: Entities the importer lands, in dependency order.
IMPORTED_ENTITIES: tuple[str, ...] = ("item", "work_centre", "warehouse")

ITEM_UPDATE_FIELDS = ("item_name", "item_group", "description")


@dataclass
class ImportResult:
	"""Outcome of importing one canonical extract."""

	source: str
	imported: dict[str, int] = field(default_factory=dict)
	documents: dict[str, list[str]] = field(default_factory=dict)

	def record(self, entity: str, doctype: str, name: str) -> None:
		self.imported[entity] = self.imported.get(entity, 0) + 1
		self.documents.setdefault(doctype, []).append(name)


def default_company() -> str:
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(frappe._("Keine Firma vorhanden — Stammdatenmigration nicht möglich."))
	return company


def warehouse_document_name(warehouse_name: str, company: str) -> str:
	"""The `Warehouse` document name ERPNext derives from name plus company abbreviation."""
	abbr = frappe.db.get_value("Company", company, "abbr")
	return f"{warehouse_name} - {abbr}"


def _set_legacy_ref(doc: Any, extract: CanonicalExtract, record: CanonicalRecord) -> None:
	"""Preserve the source identifier in `legacy_refs`, if the substrate carries it."""
	if not doc.meta.get_field("legacy_refs"):
		return
	marker = (extract.source_system, record.source_identifier)
	existing = {(row.source_system, row.source_identifier) for row in (doc.get("legacy_refs") or [])}
	if marker in existing:
		return
	doc.append(
		"legacy_refs",
		{
			"source_system": extract.source_system,
			"source_entity": record.source_entity,
			"source_identifier": record.source_identifier,
		},
	)


def _persist(doc: Any, *, existing: bool) -> str:
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return doc.name


def _import_item(extract: CanonicalExtract, record: CanonicalRecord) -> tuple[str, str]:
	item_code = record.fields["item_code"]
	existing = bool(frappe.db.exists("Item", item_code))
	if existing:
		doc = frappe.get_doc("Item", item_code)
		for name in ITEM_UPDATE_FIELDS:
			if record.fields.get(name) is not None:
				doc.set(name, record.fields[name])
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": record.fields.get("item_name"),
				"item_group": record.fields["item_group"],
				"stock_uom": record.fields["stock_uom"],
				"description": record.fields.get("description"),
				"is_stock_item": 1,
			}
		)
	_set_legacy_ref(doc, extract, record)
	return "Item", _persist(doc, existing=existing)


def _import_work_centre(extract: CanonicalExtract, record: CanonicalRecord) -> tuple[str, str]:
	workstation_name = record.fields["workstation_name"]
	existing = bool(frappe.db.exists("Workstation", workstation_name))
	if existing:
		doc = frappe.get_doc("Workstation", workstation_name)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Workstation",
				"workstation_name": workstation_name,
				"company": default_company(),
			}
		)
	_set_legacy_ref(doc, extract, record)
	return "Workstation", _persist(doc, existing=existing)


def _import_warehouse(extract: CanonicalExtract, record: CanonicalRecord) -> tuple[str, str]:
	company = default_company()
	warehouse_name = record.fields["warehouse_name"]
	name = warehouse_document_name(warehouse_name, company)
	existing = bool(frappe.db.exists("Warehouse", name))
	if existing:
		doc = frappe.get_doc("Warehouse", name)
	else:
		doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": warehouse_name, "company": company})
	_set_legacy_ref(doc, extract, record)
	return "Warehouse", _persist(doc, existing=existing)


IMPORTERS = {
	"item": _import_item,
	"work_centre": _import_work_centre,
	"warehouse": _import_warehouse,
}


def import_extract(extract: CanonicalExtract) -> ImportResult:
	"""Import a canonical extract onto the anchor DocTypes."""
	result = ImportResult(source=extract.source)
	for entity in IMPORTED_ENTITIES:
		for record in extract.of(entity):
			doctype, name = IMPORTERS[entity](extract, record)
			result.record(entity, doctype, name)
	return result
