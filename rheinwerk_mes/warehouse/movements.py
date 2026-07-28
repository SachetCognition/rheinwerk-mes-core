"""Batch-aware stock movements on the anchor ledger (URS-W1-021).

Every W1 warehouse movement is an anchor `Stock Entry` with a batch allocation, so
movement history lives in one immutable ledger (ADR-007 / CDM-05). The Qcadoo document
taxonomy (`DocumentType.java:31-35`, `SachetCognition/Chem_mes@master`) is mapped onto
Stock Entry purposes rather than re-implemented as a parallel document store.
"""

from __future__ import annotations

import frappe

#: Qcadoo `DocumentType` → anchor Stock Entry purpose (DocumentType.java:31-35).
PURPOSE_MAP: dict[str, str] = {
	"RECEIPT": "Material Receipt",
	"RELEASE": "Material Issue",
	"TRANSFER": "Material Transfer",
	"INTERNAL": "Material Transfer",
}


def stock_entry_purpose(document_type: str) -> str:
	"""Map a Qcadoo document type to the anchor Stock Entry purpose."""
	return PURPOSE_MAP[str(document_type).upper()]


def book_movement(
	*,
	document_type: str,
	item: str,
	qty: float,
	batch_no: str,
	company: str,
	source_warehouse: str | None = None,
	target_warehouse: str | None = None,
	storage_location: str | None = None,
	handling_unit: str | None = None,
	basic_rate: float | None = None,
) -> str:
	"""Post a batch-aware Stock Entry for a Qcadoo-style movement; returns its name.

	`storage_location`/`handling_unit` are recorded as references on the row (the ledger
	still owns the quantity); the batch is booked through the anchor Serial and Batch
	fields so a single Serial and Batch Bundle carries the lot allocation.
	"""
	purpose = stock_entry_purpose(document_type)
	row = {
		"item_code": item,
		"qty": qty,
		"uom": frappe.db.get_value("Item", item, "stock_uom"),
		"use_serial_batch_fields": 1,
		"batch_no": batch_no,
	}
	if source_warehouse:
		row["s_warehouse"] = source_warehouse
	if target_warehouse:
		row["t_warehouse"] = target_warehouse
	if basic_rate is not None:
		row["basic_rate"] = basic_rate
	if storage_location and frappe.get_meta("Stock Entry Detail").get_field("storage_location"):
		row["storage_location"] = storage_location
	if handling_unit and frappe.get_meta("Stock Entry Detail").get_field("handling_unit"):
		row["handling_unit"] = handling_unit

	doc = frappe.get_doc(
		{"doctype": "Stock Entry", "stock_entry_type": purpose, "company": company, "items": [row]}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name
