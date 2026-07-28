"""QA disposition of a Rejected inspection (W2-4 · URS-W2-016).

A Rejected inspection may not leave its batch undispositioned. The inspector records one of
two decisions on the inspection itself — both requiring a reason —

* **Charge sperren** (`Block Batch`) → the batch is driven to `Blocked` through the
  genealogy child's `qa_state.transition`, with the inspection as triggering document;
* **Nacharbeit zuweisen** (`Assign Rework`) → the inspection references a rework production
  order; the batch stays in its current disposition (Quarantined) and the reference is the
  audit trail of the decision.

The nightly integrity check lists every Rejected inspection without a decision
(`undispositioned_rejections`), which the inspector queue renders as its own section
(URS-W2-016 AC-2).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

BLOCK_BATCH = "Block Batch"
ASSIGN_REWORK = "Assign Rework"

DISPOSITIONS: tuple[str, ...] = (BLOCK_BATCH, ASSIGN_REWORK)

DISPOSITION_LABELS: dict[str, str] = {
	BLOCK_BATCH: "Charge sperren",
	ASSIGN_REWORK: "Nacharbeit zuweisen",
}

#: Wording of the integrity finding, rendered in the inspector's queue (URS-W2-016 AC-2).
FINDING_LABEL = "Abgelehnt ohne Verwendungsentscheid"


def choices() -> list[dict[str, str]]:
	"""The two decisions offered on a Rejected inspection (URS-W2-016 AC-1)."""
	return [{"value": value, "label": _(DISPOSITION_LABELS[value])} for value in DISPOSITIONS]


def is_dispositioned(inspection: str | dict[str, Any] | Any) -> bool:
	"""True when a decision has been recorded on this Rejected inspection."""
	if isinstance(inspection, dict):
		return bool(inspection.get("rw_disposition"))
	if isinstance(inspection, str):
		return bool(frappe.db.get_value("Quality Inspection", inspection, "rw_disposition"))
	return bool(inspection.get("rw_disposition"))


@frappe.whitelist()
def record_disposition(
	inspection: str,
	decision: str,
	reason: str,
	rework_order: str | None = None,
) -> dict[str, Any]:
	"""Record the QA decision on a Rejected inspection and drive `qa_state` accordingly."""
	from rheinwerk_mes.genealogy import qa_state

	doc = frappe.get_doc("Quality Inspection", inspection)
	if doc.status != "Rejected":
		frappe.throw(
			_("Ein Verwendungsentscheid ist nur für abgelehnte Prüfungen vorgesehen ({0}).").format(doc.name),
			title=_("Verwendungsentscheid nicht möglich"),
		)
	if decision not in DISPOSITIONS:
		frappe.throw(
			_("Unbekannter Verwendungsentscheid: {0}").format(decision),
			title=_("Verwendungsentscheid nicht möglich"),
		)
	if not (reason or "").strip():
		frappe.throw(
			_("Für den Verwendungsentscheid ist eine Begründung erforderlich."),
			title=_("Begründung fehlt"),
		)
	if decision == ASSIGN_REWORK and not rework_order:
		frappe.throw(
			_("Für die Nacharbeit ist ein Nacharbeitsauftrag anzugeben."),
			title=_("Nacharbeitsauftrag fehlt"),
		)

	doc.db_set(
		{
			"rw_disposition": decision,
			"rw_disposition_reason": reason,
			"rw_rework_order": rework_order if decision == ASSIGN_REWORK else None,
			"rw_disposition_recorded_on": now_datetime(),
		},
		update_modified=False,
	)

	if decision == BLOCK_BATCH and doc.batch_no:
		if frappe.db.get_value("Batch", doc.batch_no, "qa_state") != qa_state.BLOCKED:
			qa_state.transition(
				doc.batch_no,
				qa_state.BLOCKED,
				reason=reason,
				triggering_document=doc.name,
			)
	return {
		"inspection": doc.name,
		"batch": doc.batch_no,
		"decision": decision,
		"decision_label": _(DISPOSITION_LABELS[decision]),
		"reason": reason,
		"rework_order": rework_order if decision == ASSIGN_REWORK else None,
		"qa_state": frappe.db.get_value("Batch", doc.batch_no, "qa_state") if doc.batch_no else None,
	}


@frappe.whitelist()
def undispositioned_rejections() -> list[dict[str, Any]]:
	"""Integrity check: Rejected inspections without a decision (URS-W2-016 AC-2)."""
	rows = frappe.get_all(
		"Quality Inspection",
		filters={"docstatus": 1, "status": "Rejected", "rw_disposition": ("in", ("", None))},
		fields=["name", "batch_no", "item_code", "report_date", "quality_inspection_template"],
		order_by="report_date asc, creation asc",
	)
	for row in rows:
		row["finding"] = _(FINDING_LABEL)
	return rows
