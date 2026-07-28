"""Quality Inspection adoption (W2-4 · URS-W2-013, URS-W2-014).

The ERPNext `Quality Inspection` engine is **adopted unmodified**: parameter instantiation
from a `Quality Inspection Template`, numeric min/max evaluation, value match and
`safe_eval` acceptance formulae, and the automatic Accepted/Rejected result all stay in the
anchor (`erpnext/stock/doctype/quality_inspection/quality_inspection.py:265-336`). This
module only

* names the estate conventions on top of the anchor (which template an item carries, which
  batch and production order an inspection belongs to, the unit rendered next to a reading),
* offers a thin, German-first creation/entry API the queue page and the tests call,
* answers the questions the gates ask ("is there an accepted inspection for this batch?").

No anchor DocType is forked: the production-order reference is the Custom Field
`rw_work_order` and the two anchor `reference_*` fields are relaxed by Property Setter —
see `rheinwerk_mes/setup/w2_quality.py` and `docs/design/W2-quality-coa.md` §2.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, today
from frappe.utils.data import get_number_format_info

ACCEPTED = "Accepted"
REJECTED = "Rejected"
CANCELLED = "Cancelled"

IN_PROCESS = "In Process"
INCOMING = "Incoming"
OUTGOING = "Outgoing"

INSPECTION_TYPES: tuple[str, ...] = (INCOMING, OUTGOING, IN_PROCESS)

#: German pill labels for the inspection result (design skill — icon + label + colour).
STATUS_LABELS: dict[str, str] = {
	ACCEPTED: "Angenommen",
	REJECTED: "Abgelehnt",
	CANCELLED: "Storniert",
}

TYPE_LABELS: dict[str, str] = {
	INCOMING: "Wareneingang",
	OUTGOING: "Warenausgang",
	IN_PROCESS: "Fertigungsbegleitend",
}

#: Anchor Item field carrying the template — the estate's "inspection required" marker.
ITEM_TEMPLATE_FIELD = "quality_inspection_template"

#: Custom Field on `Quality Inspection Parameter` holding the unit rendered in the queue.
UNIT_FIELD = "rw_unit"


# --------------------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------------------


def template_for_item(item: str | None) -> str | None:
	"""The inspection template assigned to `item`, or None when it needs no inspection."""
	if not item:
		return None
	return frappe.db.get_value("Item", item, ITEM_TEMPLATE_FIELD) or None


def inspection_required(item: str | None) -> bool:
	"""True when items of this kind may not complete production uninspected (URS-W2-014)."""
	return bool(template_for_item(item))


def parameter_unit(specification: str | None) -> str:
	"""Unit of a quality parameter (mPa·s, g/cm³, %), '' when the parameter carries none."""
	if not specification or not frappe.get_meta("Quality Inspection Parameter").get_field(UNIT_FIELD):
		return ""
	return frappe.db.get_value("Quality Inspection Parameter", specification, UNIT_FIELD) or ""


def template_parameters(template: str | None) -> list[dict[str, Any]]:
	"""Parameters of `template` with their limits and units, in template order."""
	if not template:
		return []
	rows = frappe.get_all(
		"Item Quality Inspection Parameter",
		fields=[
			"specification",
			"value",
			"numeric",
			"formula_based_criteria",
			"acceptance_formula",
			"min_value",
			"max_value",
		],
		filters={"parenttype": "Quality Inspection Template", "parent": template},
		order_by="idx",
	)
	for row in rows:
		row["unit"] = parameter_unit(row["specification"])
	return rows


# --------------------------------------------------------------------------------------
# Production-order ↔ batch resolution
# --------------------------------------------------------------------------------------


def produced_batches(work_order: str) -> list[dict[str, str]]:
	"""Batches this order has produced, from its submitted receipts (`(batch, item)` rows).

	Read from the stock postings rather than from the genealogy tables so the answer is
	identical whether or not the genealogy links have been rebuilt yet.
	"""
	production_item = frappe.db.get_value("Work Order", work_order, "production_item")
	rows = frappe.db.sql(
		"""
		select distinct sed.batch_no as batch, sed.item_code as item
		from `tabStock Entry Detail` sed
		join `tabStock Entry` se on se.name = sed.parent
		where se.docstatus = 1 and se.work_order = %(order)s
		  and sed.t_warehouse is not null and sed.t_warehouse != ''
		  and sed.batch_no is not null and sed.batch_no != ''
		  and sed.item_code = %(item)s
		order by sed.batch_no
		""",
		{"order": work_order, "item": production_item},
		as_dict=True,
	)
	return [dict(row) for row in rows]


def work_order_of(inspection: str | Any) -> str | None:
	doc = _load(inspection)
	return doc.get("rw_work_order")


# --------------------------------------------------------------------------------------
# Queries the gates and the queue ask
# --------------------------------------------------------------------------------------


def inspections_for_batch(
	batch: str, status: str | None = None, docstatus: int | None = 1
) -> list[dict[str, Any]]:
	"""Inspections recorded against `batch`, newest first."""
	filters: dict[str, Any] = {"batch_no": batch}
	if status:
		filters["status"] = status
	if docstatus is not None:
		filters["docstatus"] = docstatus
	return frappe.get_all(
		"Quality Inspection",
		filters=filters,
		fields=[
			"name",
			"status",
			"docstatus",
			"inspection_type",
			"item_code",
			"batch_no",
			"report_date",
			"inspected_by",
			"quality_inspection_template",
			"rw_work_order",
			"rw_disposition",
		],
		order_by="report_date desc, creation desc",
	)


def accepted_inspection(batch: str) -> str | None:
	"""Name of the submitted Accepted inspection of `batch` (URS-W2-014 AC-3)."""
	rows = inspections_for_batch(batch, status=ACCEPTED)
	return rows[0]["name"] if rows else None


def rejected_inspections(batch: str) -> list[dict[str, Any]]:
	return inspections_for_batch(batch, status=REJECTED)


def open_inspection(batch: str) -> str | None:
	"""A draft inspection already waiting for readings, if any."""
	rows = inspections_for_batch(batch, docstatus=0)
	return rows[0]["name"] if rows else None


# --------------------------------------------------------------------------------------
# Creation and reading entry
# --------------------------------------------------------------------------------------


def _load(inspection: str | Any) -> Any:
	return frappe.get_doc("Quality Inspection", inspection) if isinstance(inspection, str) else inspection


@frappe.whitelist()
def create_inspection(
	batch: str,
	inspection_type: str = IN_PROCESS,
	work_order: str | None = None,
	sample_size: float = 1.0,
) -> Any:
	"""Instantiate an inspection for `batch` from its item's template (URS-W2-013 AC-1).

	The parameters are instantiated by the **anchor** (`get_item_specification_details`);
	this wrapper only supplies the estate's references and refuses a batch whose item
	carries no template, naming the item.
	"""
	if inspection_type not in INSPECTION_TYPES:
		frappe.throw(_("Unbekannte Prüfart: {0}").format(inspection_type), title=_("Prüfung nicht angelegt"))
	item = frappe.db.get_value("Batch", batch, "item")
	template = template_for_item(item)
	if not template:
		frappe.throw(
			_("Für den Artikel {0} ist keine Prüfvorlage hinterlegt (Charge {1}).").format(item, batch),
			title=_("Prüfung nicht angelegt"),
		)
	doc = frappe.get_doc(
		{
			"doctype": "Quality Inspection",
			"inspection_type": inspection_type,
			"report_date": today(),
			"item_code": item,
			"batch_no": batch,
			"sample_size": flt(sample_size),
			"quality_inspection_template": template,
			"inspected_by": frappe.session.user,
			"rw_work_order": work_order,
		}
	)
	doc.get_item_specification_details()
	doc.insert()
	return doc


def format_reading(value: Any) -> str:
	"""Render a reading in the site's number format (German: 1,04 — not 1.04).

	The anchor parses readings with `parse_float`, which honours the site number format, so
	a canonical `1.04` would be read as 104 on a German site. Values typed in the queue
	already arrive localised and are passed through unchanged.
	"""
	if isinstance(value, bool) or not isinstance(value, int | float):
		return "" if value is None else str(value)
	decimal_separator = get_number_format_info(frappe.db.get_default("number_format") or "#,###.##")[0]
	text = f"{value:f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
	return text.replace(".", decimal_separator)


@frappe.whitelist()
def enter_readings(inspection: str | Any, readings: dict[str, Any] | str, submit: bool = False) -> Any:
	"""Record `{parameter: value}` readings; the anchor evaluates them (URS-W2-013 AC-2/3).

	Nothing is judged here — `inspect_and_set_status` on the anchor sets every reading's
	status and the inspection result on save.
	"""
	if isinstance(readings, str):
		readings = frappe.parse_json(readings)
	doc = _load(inspection)
	for row in doc.readings:
		if row.specification in readings:
			value = format_reading(readings[row.specification])
			if row.numeric:
				row.reading_1 = value
			else:
				row.reading_value = value
	doc.save()
	if submit:
		doc.submit()
	return doc


def reading_rows(inspection: str | Any) -> list[dict[str, Any]]:
	"""Readings of `inspection` as a render-ready, German-first row set."""
	doc = _load(inspection)
	rows = []
	for row in doc.readings:
		rows.append(
			{
				"parameter": row.specification,
				"unit": parameter_unit(row.specification),
				"numeric": bool(row.numeric),
				"min_value": flt(row.min_value) if row.numeric else None,
				"max_value": flt(row.max_value) if row.numeric else None,
				"expected_value": row.value,
				"acceptance_formula": row.acceptance_formula,
				"reading": (row.reading_1 if row.numeric else row.reading_value) or "",
				"status": row.status,
				"status_label": _(STATUS_LABELS.get(row.status, row.status or "")),
			}
		)
	return rows


def failing_readings(inspection: str | Any) -> list[dict[str, Any]]:
	"""Readings that failed, with the limit they violate (URS-W2-013 AC-3)."""
	return [row for row in reading_rows(inspection) if row["status"] == REJECTED]


def limit_text(row: dict[str, Any]) -> str:
	"""German-first rendering of a reading's acceptance limit, unit included."""
	unit = f" {row['unit']}" if row.get("unit") else ""
	if row.get("acceptance_formula"):
		return row["acceptance_formula"]
	if row.get("numeric"):
		low, high = (f"{flt(value):g}".replace(".", ",") for value in (row["min_value"], row["max_value"]))
		return f"{low} – {high}{unit}"
	return f"{row.get('expected_value') or ''}"


# --------------------------------------------------------------------------------------
# Document events (registered in hooks.py)
# --------------------------------------------------------------------------------------


def on_inspection_submit(doc: Any, method: str | None = None) -> None:
	"""An Accepted inspection releases its batch (URS-W2-014 AC-3 / TC-W2-021).

	The disposition itself stays with the genealogy child's state machine — this hook only
	names the inspection as the triggering document. A Rejected inspection is *not*
	dispositioned automatically: URS-W2-016 requires an explicit human decision.
	"""
	from rheinwerk_mes.genealogy import qa_state

	if not doc.batch_no or doc.status != ACCEPTED:
		return
	if not frappe.get_meta("Batch").get_field("qa_state"):
		return
	if frappe.db.get_value("Batch", doc.batch_no, "qa_state") == qa_state.RELEASED:
		return
	qa_state.transition(
		doc.batch_no,
		qa_state.RELEASED,
		reason=_("Qualitätsprüfung {0} angenommen").format(doc.name),
		triggering_document=doc.name,
	)
