"""Inspection queue view model for the quality inspector (W2-4 · URS-W2-015).

Layout pattern 1 of the design skill — *Work Queue → Detail*: the left column is the list
of due inspections (batch chip, item, type, due indication), the right column is the
detail of the selected row with its reading inputs. Everything the Desk page renders is
pre-composed here (German-first labels, DD.MM.YYYY dates, units suffixed inside the
inputs), so the Desk and Terminal renderings cannot drift apart.

A "due" inspection is either a draft inspection waiting for readings, or a batch that
requires one and has none — the queue therefore also covers the state the QI gate refuses
completion for (URS-W2-014 AC-1). The Rejected-without-disposition findings of the nightly
integrity check are a section of the same queue (URS-W2-016 AC-2).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import formatdate

from rheinwerk_mes.genealogy import qa_state
from rheinwerk_mes.quality import disposition, inspections

#: Shown when nothing is due — the empty state directs, never decorates (AC-3).
EMPTY_STATE_TITLE = "Keine Prüfungen fällig"


def _german_date(value: Any) -> str:
	return formatdate(value, "dd.MM.yyyy") if value else ""


def _batch_chip(batch: str) -> dict[str, Any]:
	row = (
		frappe.db.get_value(
			"Batch", batch, ["item", "qa_state", "expiry_date", "manufacturing_date"], as_dict=True
		)
		or {}
	)
	state = row.get("qa_state") or qa_state.INITIAL_STATE
	return {
		"batch": batch,
		"item": row.get("item"),
		"qa_state": state,
		"qa_state_label": _(qa_state.STATE_LABELS.get(state, state)),
		"expiry_date": _german_date(row.get("expiry_date")),
		"manufacturing_date": _german_date(row.get("manufacturing_date")),
	}


def _due_from_drafts(filters: dict[str, Any]) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		"Quality Inspection",
		filters={"docstatus": 0, **filters},
		fields=[
			"name",
			"batch_no",
			"item_code",
			"inspection_type",
			"report_date",
			"quality_inspection_template",
			"rw_work_order",
		],
		order_by="report_date asc, creation asc",
	)
	return [
		{
			"inspection": row["name"],
			"batch": row["batch_no"],
			"item": row["item_code"],
			"inspection_type": row["inspection_type"],
			"type_label": _(inspections.TYPE_LABELS.get(row["inspection_type"], row["inspection_type"])),
			"template": row["quality_inspection_template"],
			"production_order": row["rw_work_order"],
			"due_date": _german_date(row["report_date"]),
			"due_reason": _("Messwerte erfassen"),
			"chip": _batch_chip(row["batch_no"]) if row["batch_no"] else None,
		}
		for row in rows
		if row["batch_no"]
	]


def _due_from_uninspected_batches(
	item: str | None, batch: str | None, production_order: str | None
) -> list[dict[str, Any]]:
	"""Quarantined batches whose item carries a template but which have no inspection yet."""
	filters: dict[str, Any] = {"qa_state": qa_state.QUARANTINED}
	if item:
		filters["item"] = item
	if batch:
		filters["name"] = batch
	rows = frappe.get_all(
		"Batch",
		filters=filters,
		fields=["name", "item", "expiry_date"],
		order_by="creation asc",
		limit_page_length=0,
	)
	due = []
	for row in rows:
		template = inspections.template_for_item(row["item"])
		if not template or inspections.inspections_for_batch(row["name"], docstatus=None):
			continue
		order = _production_order_of(row["name"])
		if production_order and order != production_order:
			continue
		due.append(
			{
				"inspection": None,
				"batch": row["name"],
				"item": row["item"],
				"inspection_type": inspections.IN_PROCESS,
				"type_label": _(inspections.TYPE_LABELS[inspections.IN_PROCESS]),
				"template": template,
				"production_order": order,
				"due_date": "",
				"due_reason": _("Prüfung anlegen"),
				"chip": _batch_chip(row["name"]),
			}
		)
	return due


def _production_order_of(batch: str) -> str | None:
	return frappe.db.get_value(
		"Genealogy Link", {"parent": batch, "direction": "produced"}, "production_order"
	)


@frappe.whitelist()
def inspection_queue(
	inspection_type: str | None = None,
	item: str | None = None,
	batch: str | None = None,
	production_order: str | None = None,
) -> dict[str, Any]:
	"""The inspector's work queue (URS-W2-015 AC-1/AC-3), filterable on all four axes."""
	draft_filters: dict[str, Any] = {}
	if inspection_type:
		draft_filters["inspection_type"] = inspection_type
	if item:
		draft_filters["item_code"] = item
	if batch:
		draft_filters["batch_no"] = batch
	if production_order:
		draft_filters["rw_work_order"] = production_order

	rows = _due_from_drafts(draft_filters)
	if not inspection_type or inspection_type == inspections.IN_PROCESS:
		rows += _due_from_uninspected_batches(item, batch, production_order)

	findings = disposition.undispositioned_rejections()
	return {
		"rows": rows,
		"count": len(rows),
		"findings": [
			{
				"inspection": row["name"],
				"batch": row["batch_no"],
				"item": row["item_code"],
				"finding": row["finding"],
				"choices": disposition.choices(),
			}
			for row in findings
		],
		"filters": {
			"inspection_type": inspection_type,
			"item": item,
			"batch": batch,
			"production_order": production_order,
		},
		"empty_state": empty_state(bool(rows)),
	}


def empty_state(has_rows: bool) -> dict[str, Any] | None:
	"""Directive empty state naming the next scheduled inspection (URS-W2-015 AC-3)."""
	if has_rows:
		return None
	next_due = frappe.get_all(
		"Quality Inspection",
		filters={"docstatus": 0},
		fields=["name", "report_date"],
		order_by="report_date asc",
		limit=1,
	)
	if next_due:
		hint = _("Nächste geplante Prüfung: {0} am {1}.").format(
			next_due[0]["name"], _german_date(next_due[0]["report_date"])
		)
	else:
		hint = _("Nächste geplante Prüfung: keine terminiert. Prüfung über eine Charge anlegen.")
	return {"title": _(EMPTY_STATE_TITLE), "hint": hint}


@frappe.whitelist()
def inspection_detail(inspection: str) -> dict[str, Any]:
	"""Detail pane of a queued inspection — reading inputs with suffixed units (AC-2)."""
	doc = frappe.get_doc("Quality Inspection", inspection)
	doc.check_permission("read")
	return {
		"inspection": doc.name,
		"batch": doc.batch_no,
		"item": doc.item_code,
		"inspection_type": doc.inspection_type,
		"type_label": _(inspections.TYPE_LABELS.get(doc.inspection_type, doc.inspection_type)),
		"template": doc.quality_inspection_template,
		"production_order": doc.get("rw_work_order"),
		"report_date": _german_date(doc.report_date),
		"status": doc.status,
		"status_label": _(inspections.STATUS_LABELS.get(doc.status, doc.status or "")),
		"submitted": doc.docstatus == 1,
		"chip": _batch_chip(doc.batch_no) if doc.batch_no else None,
		"readings": [
			{
				**row,
				"limit_text": inspections.limit_text(row),
				"unit_suffix": row["unit"],
				"label": row["parameter"],
			}
			for row in inspections.reading_rows(doc)
		],
		"disposition": {
			"required": doc.status == inspections.REJECTED and not disposition.is_dispositioned(doc),
			"recorded": doc.get("rw_disposition"),
			"reason": doc.get("rw_disposition_reason"),
			"rework_order": doc.get("rw_rework_order"),
			"choices": disposition.choices(),
		},
	}
