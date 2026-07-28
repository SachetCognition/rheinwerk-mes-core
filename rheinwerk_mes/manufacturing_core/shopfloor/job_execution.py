"""Job-card execution on the anchor Job Card (W1-7 · URS-W1-026, URS-W1-027).

Adopted substrate: `erpnext/manufacturing/doctype/job_card/job_card.py:1280-1397`
(`set_status`, `pause_job`, `resume_job`) and `:912-959` (submission is refused while the
card is On Hold). The anchor DocType is never forked — this module only drives anchor
fields (`time_logs`, `is_paused`, `total_completed_qty`) and anchor methods, and adds the
German-first operator vocabulary plus the `exec_state` reconciliation the plant needs.

Public surface (all whitelisted, called from `rheinwerk_mes/public/js/shopfloor.js`):

* `job_queue(work_order)` — the operator's queue for one production order.
* `start_job(job_card)` / `pause_job` / `resume_job` — time-log lifecycle.
* `record_output(job_card, completed_qty, submit=False)` — output recording.
* `order_output(work_order)` — recorded output reconciled with `exec_state` completion.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, time_diff_in_seconds

from rheinwerk_mes.manufacturing_core.shopfloor.formatting import (
	format_datetime_de,
	format_kg,
	format_minutes,
)
from rheinwerk_mes.manufacturing_core.shopfloor.terminal import state_pill

ON_HOLD = "On Hold"
WORK_IN_PROGRESS = "Work In Progress"


def _minutes_between(to_time: Any, from_time: Any) -> float:
	"""Duration of a time log in minutes, matching the anchor's own rounding."""
	return flt(time_diff_in_seconds(to_time, from_time) / 60.0, 6)


def _load(job_card: Any) -> Any:
	return frappe.get_doc("Job Card", job_card) if isinstance(job_card, str) else job_card


def _open_time_log(doc: Any) -> Any | None:
	"""The running time log — a row with a start and no end (anchor `add_time_logs`)."""
	for row in reversed(doc.get("time_logs") or []):
		if row.from_time and not row.to_time:
			return row
	return None


def job_card_view(doc: Any) -> dict[str, Any]:
	"""One Terminal Card payload: the current task, rendered German-first."""
	return {
		"job_card": doc.name,
		"work_order": doc.work_order,
		"operation": doc.operation,
		"workstation": doc.workstation,
		"job_status": doc.status,
		"status_pill": state_pill(doc.status),
		"is_paused": int(doc.get("is_paused") or 0),
		"for_quantity": flt(doc.for_quantity),
		"for_quantity_display": format_kg(doc.for_quantity),
		"total_completed_qty": flt(doc.total_completed_qty),
		"total_completed_qty_display": format_kg(doc.total_completed_qty),
		"docstatus": doc.docstatus,
		"time_logs": [
			{
				"from_time": format_datetime_de(row.from_time),
				"to_time": format_datetime_de(row.to_time),
				"time_in_mins": flt(row.time_in_mins),
				"duration_display": format_minutes(row.time_in_mins),
				"completed_qty": flt(row.completed_qty),
			}
			for row in doc.get("time_logs") or []
		],
	}


@frappe.whitelist()
def job_queue(work_order: str) -> dict[str, Any]:
	"""Job cards of one production order, in operation sequence (URS-W1-026 AC-1)."""
	if not frappe.db.exists("Work Order", work_order):
		frappe.throw(
			_("Fertigungsauftrag {0} ist nicht bekannt.").format(work_order), frappe.DoesNotExistError
		)
	order = frappe.get_doc("Work Order", work_order)
	names = frappe.get_all(
		"Job Card",
		filters={"work_order": work_order, "docstatus": ("<", 2)},
		order_by="sequence_id asc, creation asc",
		pluck="name",
	)
	return {
		"work_order": order.name,
		"production_item": order.production_item,
		"exec_state": order.get("exec_state"),
		"exec_state_pill": state_pill(order.get("exec_state")),
		"qty_display": format_kg(order.qty),
		"produced_qty_display": format_kg(order.produced_qty),
		"jobs": [job_card_view(frappe.get_doc("Job Card", name)) for name in names],
	}


@frappe.whitelist()
def start_job(job_card: str, employee: str | None = None) -> dict[str, Any]:
	"""Open a time log on the card — the operator's "Arbeit starten" (URS-W1-026 AC-2)."""
	doc = _load(job_card)
	_assert_writable(doc)
	if doc.get("is_paused"):
		frappe.throw(
			_("Arbeitsgang {0} ist pausiert. Bitte zuerst fortsetzen.").format(doc.name),
			title=_("Aktion abgelehnt"),
		)
	if _open_time_log(doc):
		frappe.throw(
			_("Für Arbeitsgang {0} läuft bereits eine Zeiterfassung.").format(doc.name),
			title=_("Aktion abgelehnt"),
		)
	doc.append("time_logs", {"from_time": now_datetime(), "completed_qty": 0.0, "employee": employee})
	doc.save()
	doc.reload()
	return job_card_view(doc)


@frappe.whitelist()
def stop_job(job_card: str, completed_qty: float | None = None) -> dict[str, Any]:
	"""Close the running time log with start/end and computed duration (URS-W1-026 AC-2)."""
	doc = _load(job_card)
	_assert_writable(doc)
	row = _open_time_log(doc)
	if not row:
		frappe.throw(
			_("Für Arbeitsgang {0} läuft keine Zeiterfassung.").format(doc.name),
			title=_("Aktion abgelehnt"),
		)
	row.to_time = now_datetime()
	row.time_in_mins = _minutes_between(row.to_time, row.from_time)
	if completed_qty is not None:
		row.completed_qty = flt(completed_qty)
	doc.save()
	doc.reload()
	return job_card_view(doc)


@frappe.whitelist()
def pause_job(job_card: str) -> dict[str, Any]:
	"""Pause the card (anchor On Hold) and close the open time log (URS-W1-027 AC-1).

	Delegates to the anchor `Job Card.pause_job` (`job_card.py:1371-1381`) so the substrate
	keeps owning `is_paused` and the status derivation.
	"""
	doc = _load(job_card)
	_assert_writable(doc)
	if doc.get("is_paused"):
		frappe.throw(_("Arbeitsgang {0} ist bereits pausiert.").format(doc.name), title=_("Aktion abgelehnt"))
	if not _open_time_log(doc):
		frappe.throw(
			_("Für Arbeitsgang {0} läuft keine Zeiterfassung.").format(doc.name),
			title=_("Aktion abgelehnt"),
		)
	doc.pause_job(end_time=now_datetime())
	doc.reload()
	doc.set_status(update_status=True)
	doc.reload()
	return job_card_view(doc)


@frappe.whitelist()
def resume_job(job_card: str, employee: str | None = None) -> dict[str, Any]:
	"""Resume a paused card: a fresh time log, back to Work In Progress (URS-W1-027 AC-1).

	Re-expresses the anchor `resume_job` (`job_card.py:1383-1397`) for the unmanned shop-floor
	terminal, where a card is worked without an Employee record and the anchor's
	employee-keyed path has nothing to iterate.
	"""
	doc = _load(job_card)
	_assert_writable(doc)
	if not doc.get("is_paused"):
		frappe.throw(_("Arbeitsgang {0} ist nicht pausiert.").format(doc.name), title=_("Aktion abgelehnt"))
	doc.db_set("is_paused", 0)
	doc.reload()
	doc.append("time_logs", {"from_time": now_datetime(), "completed_qty": 0.0, "employee": employee})
	doc.save()
	doc.reload()
	doc.set_status(update_status=True)
	doc.reload()
	return job_card_view(doc)


@frappe.whitelist()
def record_output(job_card: str, completed_qty: float, submit: bool = False) -> dict[str, Any]:
	"""Record produced quantity in kg on the card, optionally submitting it (URS-W1-026 AC-3).

	Submission stays the anchor's: a card On Hold is refused by `job_card.py:912-959`
	(URS-W1-027 AC-2), and the refusal is re-stated in the plant's voice.
	"""
	doc = _load(job_card)
	_assert_writable(doc)
	quantity = flt(completed_qty)
	if quantity <= 0:
		frappe.throw(_("Die Fertigmeldung benötigt eine Menge größer als 0 kg."))

	row = _open_time_log(doc)
	if row:
		row.to_time = now_datetime()
		row.time_in_mins = _minutes_between(row.to_time, row.from_time)
		row.completed_qty = quantity
	elif doc.get("time_logs"):
		doc.time_logs[-1].completed_qty = quantity
	else:
		now = now_datetime()
		doc.append(
			"time_logs", {"from_time": now, "to_time": now, "time_in_mins": 0.0, "completed_qty": quantity}
		)
	doc.save()

	if frappe.parse_json(submit) if isinstance(submit, str) else submit:
		if doc.get("is_paused"):
			frappe.throw(
				_(
					"Arbeitsgang {0} ist pausiert (Zustand {1}). Bitte zuerst fortsetzen, dann fertig melden."
				).format(doc.name, _(ON_HOLD)),
				title=_("Fertigmeldung abgelehnt"),
			)
		doc.submit()
	doc.reload()
	return job_card_view(doc)


@frappe.whitelist()
def order_output(work_order: str) -> dict[str, Any]:
	"""Output recorded against an order — the input of the `exec_state` completion gate.

	`exec_state` completion (URS-W1-004) compares produced with ordered quantity; the
	shop-floor journey feeds it from the submitted job cards so the two never disagree.
	"""
	order = frappe.get_doc("Work Order", work_order)
	booked = frappe.get_all(
		"Job Card",
		filters={"work_order": work_order, "docstatus": 1},
		fields=["total_completed_qty"],
		order_by="sequence_id asc, creation asc",
	)
	recorded = sum(flt(row.total_completed_qty) for row in booked)
	# The order's output is what the *last* operation produced; earlier operations feed it.
	last_operation = flt(booked[-1].total_completed_qty) if booked else 0.0
	return {
		"work_order": order.name,
		"recorded_output": last_operation,
		"recorded_output_display": format_kg(last_operation),
		"all_operations_output": recorded,
		"ordered_qty": flt(order.qty),
		"ordered_qty_display": format_kg(order.qty),
		"exec_state": order.get("exec_state"),
	}


def _assert_writable(doc: Any) -> None:
	"""Refuse execution actions on a submitted or cancelled card, in the plant's voice."""
	frappe.has_permission("Job Card", "write", doc=doc, throw=True)
	if doc.docstatus != 0:
		frappe.throw(
			_("Arbeitsgang {0} ist bereits gebucht und kann nicht mehr bearbeitet werden.").format(doc.name),
			title=_("Aktion abgelehnt"),
		)
