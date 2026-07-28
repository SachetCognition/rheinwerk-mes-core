"""Canonical-extract importer with a reversible run journal (URS-W0-008…011).

Every canonical record lands on an **anchor ERPNext DocType** (`Item`, `Workstation`,
`Warehouse`) — nothing is forked; the source identifier is preserved in the `legacy_refs`
Custom Field created by `rheinwerk_mes.setup.custom_fields`, so the identifier store stays
singular across the programme (URS-W0-014).

Each import writes a **run journal** (`<site>/private/files/rheinwerk_mes_migration/
<run_id>.json`) recording, per touched document, whether it was inserted or updated and
what its previous values were. `rollback.rollback_run` replays that journal backwards, so
a failed reconciliation removes exactly the records its own run imported and nothing else
(URS-W0-011 AC-3).

`recipe_header` records are extracted (URS-W0-008/009 require the technology/BOM headers)
but **not** imported in W0: BOM creation is governed by the CDM-04 `Recipe Governance`
workflow delivered in W1. They are reported as deferred in the run summary rather than
dropped silently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import frappe

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord

JOURNAL_DIRECTORY = "rheinwerk_mes_migration"

#: Entities the W0 importer lands; `recipe_header` is deferred to W1 (CDM-04 governance).
IMPORTED_ENTITIES = ("item", "uom_conversion", "work_centre", "warehouse")

ITEM_UPDATE_FIELDS = ("item_name", "item_group", "description")


@dataclass
class JournalEntry:
	"""One document touched by an import run."""

	doctype: str
	name: str
	action: str  # "insert" | "update"
	previous: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
	"""Outcome of importing one canonical extract."""

	run_id: str
	source: str
	imported: dict[str, int]
	deferred: dict[str, int]
	journal: list[JournalEntry]

	def as_dict(self) -> dict[str, Any]:
		return {
			"run_id": self.run_id,
			"source": self.source,
			"imported": self.imported,
			"deferred": self.deferred,
			"journal": [asdict(entry) for entry in self.journal],
		}


def journal_path(run_id: str) -> str:
	import os

	directory = frappe.get_site_path("private", "files", JOURNAL_DIRECTORY)
	os.makedirs(directory, exist_ok=True)
	return os.path.join(directory, f"{run_id}.json")


def new_run_id(source: str) -> str:
	stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S%f")
	return f"{source}-{stamp}"


def default_company() -> str:
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(frappe._("Keine Firma vorhanden — Stammdatenmigration nicht möglich."))
	return company


def warehouse_name_of(warehouse_name: str, company: str) -> str:
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


def _snapshot(doc: Any, fieldnames: tuple[str, ...]) -> dict[str, Any]:
	snapshot: dict[str, Any] = {name: doc.get(name) for name in fieldnames}
	snapshot["legacy_refs"] = [
		{
			"source_system": row.source_system,
			"source_entity": row.source_entity,
			"source_identifier": row.source_identifier,
		}
		for row in (doc.get("legacy_refs") or [])
	]
	return snapshot


def _import_item(extract: CanonicalExtract, record: CanonicalRecord) -> JournalEntry:
	item_code = record.fields["item_code"]
	if frappe.db.exists("Item", item_code):
		doc = frappe.get_doc("Item", item_code)
		previous = _snapshot(doc, ITEM_UPDATE_FIELDS)
		for name in ITEM_UPDATE_FIELDS:
			if record.fields.get(name) is not None:
				doc.set(name, record.fields[name])
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return JournalEntry("Item", doc.name, "update", previous)

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
	return JournalEntry("Item", doc.name, "insert")


def _import_uom_conversion(extract: CanonicalExtract, record: CanonicalRecord) -> JournalEntry | None:
	item_code = record.fields["item_code"]
	if not frappe.db.exists("Item", item_code):
		return None
	doc = frappe.get_doc("Item", item_code)
	previous = {
		"uoms": [{"uom": row.uom, "conversion_factor": row.conversion_factor} for row in doc.uoms],
	}
	uom = record.fields["uom"]
	factor = float(record.fields["conversion_factor"])
	for row in doc.uoms:
		if row.uom == uom:
			row.conversion_factor = factor
			break
	else:
		doc.append("uoms", {"uom": uom, "conversion_factor": factor})
	doc.save(ignore_permissions=True)
	return JournalEntry("Item", doc.name, "update", previous)


def _import_work_centre(extract: CanonicalExtract, record: CanonicalRecord) -> JournalEntry:
	name = record.fields["workstation_name"]
	values = {
		"production_line": record.fields.get("production_line")
		if frappe.db.exists("Production Line", record.fields.get("production_line") or "")
		else None,
		"division": record.fields.get("division")
		if frappe.db.exists("Division", record.fields.get("division") or "")
		else None,
	}
	if frappe.db.exists("Workstation", name):
		doc = frappe.get_doc("Workstation", name)
		previous = _snapshot(doc, ("production_line", "division"))
		doc.update({key: value for key, value in values.items() if value})
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return JournalEntry("Workstation", doc.name, "update", previous)

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
	return JournalEntry("Workstation", doc.name, "insert")


def _import_warehouse(extract: CanonicalExtract, record: CanonicalRecord) -> JournalEntry:
	company = default_company()
	warehouse_name = record.fields["warehouse_name"]
	name = warehouse_name_of(warehouse_name, company)
	disposal_method = record.fields.get("disposal_method")
	if frappe.db.exists("Warehouse", name):
		doc = frappe.get_doc("Warehouse", name)
		previous = _snapshot(doc, ("disposal_method",))
		if disposal_method and doc.meta.get_field("disposal_method"):
			doc.disposal_method = disposal_method
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return JournalEntry("Warehouse", doc.name, "update", previous)

	doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": warehouse_name, "company": company})
	if disposal_method and doc.meta.get_field("disposal_method"):
		doc.disposal_method = disposal_method
	_set_legacy_ref(doc, extract, record)
	doc.insert(ignore_permissions=True)
	return JournalEntry("Warehouse", doc.name, "insert")


IMPORTERS = {
	"item": _import_item,
	"uom_conversion": _import_uom_conversion,
	"work_centre": _import_work_centre,
	"warehouse": _import_warehouse,
}


def import_extract(extract: CanonicalExtract, *, run_id: str | None = None) -> ImportResult:
	"""Import a canonical extract, journaling every touched document."""
	run_id = run_id or new_run_id(extract.source)
	journal: list[JournalEntry] = []
	imported: dict[str, int] = {}

	for entity in IMPORTED_ENTITIES:
		for record in sorted(extract.of(entity), key=lambda item: item.key):
			entry = IMPORTERS[entity](extract, record)
			if entry is None:
				continue
			journal.append(entry)
			imported[entity] = imported.get(entity, 0) + 1

	deferred = {entity: len(extract.of(entity)) for entity in ("recipe_header",) if extract.of(entity)}
	result = ImportResult(
		run_id=run_id, source=extract.source, imported=imported, deferred=deferred, journal=journal
	)
	write_journal(result)
	return result


def write_journal(result: ImportResult) -> str:
	"""Persist the rollback journal of one run.

	A journalled *previous* field value comes straight out of the database, so it can be a
	`date`, `datetime` or `Decimal` — none of which the JSON encoder knows. They are written
	in their ISO/decimal string form, which is exactly what the rollback assigns back through
	`db.set_value`, and which `read_journal` reads without conversion.
	"""
	path = journal_path(result.run_id)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(result.as_dict(), handle, indent="\t", sort_keys=True, ensure_ascii=False, default=str)
	return path


def read_journal(run_id: str) -> ImportResult:
	with open(journal_path(run_id), encoding="utf-8") as handle:
		payload = json.load(handle)
	return ImportResult(
		run_id=payload["run_id"],
		source=payload["source"],
		imported=payload.get("imported", {}),
		deferred=payload.get("deferred", {}),
		journal=[JournalEntry(**entry) for entry in payload.get("journal", [])],
	)
