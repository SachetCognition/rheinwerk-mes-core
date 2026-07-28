"""Re-exporter: target site → canonical format (URS-W0-011).

The round trip is only meaningful if the re-export is produced the same way for every
source, from the *target* anchor DocTypes, and compared against the source extract by
natural key. The re-export therefore mirrors the source extract's entity/key set: for each
extracted record it reads the imported document back and emits the canonical fields; a
record that never arrived is simply absent, which the reconciliation reports as a count
mismatch.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord
from rheinwerk_mes.integration.migration.importer import (
	IMPORTED_ENTITIES,
	default_company,
	warehouse_name_of,
)


def _export_item(record: CanonicalRecord) -> dict[str, Any] | None:
	item_code = record.fields["item_code"]
	if not frappe.db.exists("Item", item_code):
		return None
	doc = frappe.get_doc("Item", item_code)
	return {
		"item_code": doc.item_code,
		"item_name": doc.item_name,
		"item_group": doc.item_group,
		"stock_uom": doc.stock_uom,
		"description": doc.description,
	}


def _export_uom_conversion(record: CanonicalRecord) -> dict[str, Any] | None:
	item_code = record.fields["item_code"]
	if not frappe.db.exists("Item", item_code):
		return None
	doc = frappe.get_doc("Item", item_code)
	for row in doc.uoms:
		if row.uom == record.fields["uom"]:
			return {
				"item_code": item_code,
				"uom": row.uom,
				"conversion_factor": float(row.conversion_factor),
			}
	return None


def _export_work_centre(record: CanonicalRecord) -> dict[str, Any] | None:
	name = record.fields["workstation_name"]
	if not frappe.db.exists("Workstation", name):
		return None
	doc = frappe.get_doc("Workstation", name)
	return {
		"workstation_name": doc.workstation_name,
		"production_line": doc.get("production_line") or None,
		"division": doc.get("division") or None,
	}


def _export_warehouse(record: CanonicalRecord) -> dict[str, Any] | None:
	name = warehouse_name_of(record.fields["warehouse_name"], default_company())
	if not frappe.db.exists("Warehouse", name):
		return None
	doc = frappe.get_doc("Warehouse", name)
	return {
		"warehouse_name": doc.warehouse_name,
		"disposal_method": doc.get("disposal_method") or None,
	}


EXPORTERS = {
	"item": _export_item,
	"uom_conversion": _export_uom_conversion,
	"work_centre": _export_work_centre,
	"warehouse": _export_warehouse,
}


def reexport(extract: CanonicalExtract) -> CanonicalExtract:
	"""Read the imported records back out of the target as a canonical extract."""
	records: list[CanonicalRecord] = []
	for entity in IMPORTED_ENTITIES:
		for record in extract.of(entity):
			fields = EXPORTERS[entity](record)
			if fields is None:
				continue
			records.append(
				CanonicalRecord(
					entity=entity,
					key=record.key,
					fields=fields,
					source_entity=record.source_entity,
					source_identifier=record.source_identifier,
				)
			)
	return CanonicalExtract(
		source=extract.source, records=tuple(records), direct_fields=extract.direct_fields
	)
