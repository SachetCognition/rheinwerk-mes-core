"""Canonical-extract importer for the Work Centre entity (URS-W0-005, CDM-08, ADR-010).

Every canonical `work_centre` record lands on the **anchor `Workstation` DocType** —
nothing is forked; the OFBiz FixedAsset source identifier is preserved in the `legacy_refs`
Custom Field created by `rheinwerk_mes.setup.custom_fields`. Asset accounting stays with
the group ERP: this importer creates Workstations only and never an ERPNext `Asset`
(ADR-010, ADR-002).

The importer does not commit; callers (the migration CLI, tests) own the transaction
boundary so a failed run can be rolled back cleanly.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord


def default_company() -> str:
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(frappe._("Keine Firma vorhanden — Stammdatenmigration nicht möglich."))
	return company


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


def _import_work_centre(extract: CanonicalExtract, record: CanonicalRecord) -> str:
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
		doc.update({key: value for key, value in values.items() if value})
		_set_legacy_ref(doc, extract, record)
		doc.save(ignore_permissions=True)
		return doc.name

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
	return doc.name


def import_extract(extract: CanonicalExtract) -> list[str]:
	"""Import the `work_centre` records of a canonical extract; return the Workstation names."""
	return [
		_import_work_centre(extract, record)
		for record in sorted(extract.of("work_centre"), key=lambda item: item.key)
	]
