"""Read API behind the schedule board page (W3-2 · URS-W3-005, URS-W3-020).

The board must render a 200-order line schedule in ≤ 2 s with a virtualized table
(URS-W3-020 AC-1), so the server hands out **pages** of pre-formatted rows instead of whole
documents: one query for the schedule head, one for the requested slice of entries, and no
per-row document loads. Formatting happens here (DD.MM.YYYY HH:MM, `500 kg` with a decimal
comma, state labels from the glossary), which keeps the client free of locale logic and the
payload small.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime

from .changeover import NO_NORM_NOTE
from .schedule_state import STATES, allowed_targets, state_labels

#: Page size the board requests; the table virtualizes beyond it (design skill §Tables).
DEFAULT_PAGE_LENGTH = 100

STATE_INDICATORS: dict[str, str] = {
	"Draft": "orange",
	"Approved": "green",
	"Rejected": "red",
}


def de_datetime(value: Any) -> str:
	"""DD.MM.YYYY HH:MM — the programme's date format (URS-W3-022 AC-1)."""
	if not value:
		return ""
	return get_datetime(value).strftime("%d.%m.%Y %H:%M")


def kg(value: Any) -> str:
	"""German-first mass rendering with a decimal comma and the unit kg."""
	text = f"{float(value or 0):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


def minutes(value: Any) -> str:
	"""Whole minutes with the German abbreviation."""
	return _("{0} min").format(int(value or 0))


def note_label(note: str | None) -> str:
	"""Translate the machine-readable changeover annotation (URS-W3-007 AC-2)."""
	if not note:
		return ""
	if note == NO_NORM_NOTE:
		return _("keine Umrüstnorm")
	return note


@frappe.whitelist()
def board_head(schedule: str) -> dict[str, Any]:
	"""Schedule head: line, state pill, planned start and the entry count."""
	doc = frappe.db.get_value(
		"Line Schedule",
		schedule,
		[
			"name",
			"production_line",
			"schedule_state",
			"is_operative",
			"planned_start",
			"decided_by",
			"decided_at",
		],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("Linienplan {0} existiert nicht.").format(schedule))
	labels = state_labels()
	return {
		"name": doc.name,
		"production_line": doc.production_line,
		"schedule_state": doc.schedule_state,
		"schedule_state_label": labels.get(doc.schedule_state, doc.schedule_state),
		"schedule_state_indicator": STATE_INDICATORS.get(doc.schedule_state, "gray"),
		"is_operative": bool(doc.is_operative),
		"planned_start": de_datetime(doc.planned_start),
		"decided_by": doc.decided_by,
		"decided_at": de_datetime(doc.decided_at),
		"allowed_targets": [
			labels.get(state, state) for state in sorted(allowed_targets(doc.schedule_state))
		],
		"total_entries": frappe.db.count("Line Schedule Entry", {"parent": schedule}),
	}


@frappe.whitelist()
def board_rows(schedule: str, start: int = 0, page_length: int = DEFAULT_PAGE_LENGTH) -> dict[str, Any]:
	"""One page of formatted schedule rows — the virtualized table's data source."""
	start = int(start or 0)
	page_length = max(1, int(page_length or DEFAULT_PAGE_LENGTH))
	rows = frappe.get_all(
		"Line Schedule Entry",
		filters={"parent": schedule},
		fields=[
			"sequence",
			"work_order",
			"production_item",
			"quantity",
			"exec_state",
			"realization_min",
			"changeover_min",
			"changeover_note",
			"planned_start",
			"planned_end",
		],
		order_by="sequence asc",
		start=start,
		page_length=page_length,
	)
	return {
		"start": start,
		"page_length": page_length,
		"total": frappe.db.count("Line Schedule Entry", {"parent": schedule}),
		"rows": [
			{
				"sequence": row["sequence"],
				"work_order": row["work_order"],
				"production_item": row["production_item"],
				"quantity": kg(row["quantity"]),
				"exec_state": row.get("exec_state"),
				"exec_state_label": _(row["exec_state"]) if row.get("exec_state") else "",
				"realization": minutes(row["realization_min"]),
				"changeover": minutes(row["changeover_min"]),
				"changeover_note": note_label(row.get("changeover_note")),
				"planned_start": de_datetime(row["planned_start"]),
				"planned_end": de_datetime(row["planned_end"]),
			}
			for row in rows
		],
	}


@frappe.whitelist()
def board_operations(schedule: str, work_order: str) -> list[dict[str, Any]]:
	"""TJ/TPZ breakdown of one scheduled order — the detail pane of the board."""
	rows = frappe.get_all(
		"Line Schedule Operation",
		filters={"parent": schedule, "work_order": work_order},
		fields=[
			"sequence",
			"operation",
			"workstation",
			"tpz_min",
			"tj_min_per_unit",
			"setup_min",
			"run_min",
			"duration_min",
			"planned_start",
			"planned_end",
		],
		order_by="sequence asc",
		limit_page_length=0,
	)
	return [
		{
			"sequence": row["sequence"],
			"operation": row["operation"],
			"workstation": row["workstation"],
			"tpz": minutes(row["tpz_min"]),
			"tj": _("{0} min/kg").format(str(row["tj_min_per_unit"]).replace(".", ",")),
			"setup": minutes(row["setup_min"]),
			"run": minutes(row["run_min"]),
			"duration": minutes(row["duration_min"]),
			"planned_start": de_datetime(row["planned_start"]),
			"planned_end": de_datetime(row["planned_end"]),
		}
		for row in rows
	]


@frappe.whitelist()
def line_schedules(production_line: str | None = None) -> list[dict[str, Any]]:
	"""Schedules the planner can open, newest first — the board's work queue."""
	filters = {"production_line": production_line} if production_line else {}
	labels = state_labels()
	return [
		{
			"name": row["name"],
			"production_line": row["production_line"],
			"schedule_state": row["schedule_state"],
			"schedule_state_label": labels.get(row["schedule_state"], row["schedule_state"]),
			"schedule_state_indicator": STATE_INDICATORS.get(row["schedule_state"], "gray"),
			"is_operative": bool(row["is_operative"]),
			"planned_start": de_datetime(row["planned_start"]),
		}
		for row in frappe.get_all(
			"Line Schedule",
			filters=filters,
			fields=["name", "production_line", "schedule_state", "is_operative", "planned_start"],
			order_by="creation desc",
			limit_page_length=0,
		)
	]


def glossary() -> dict[str, str]:
	"""Every schedule-state label the board renders (URS-W3-022 AC-1)."""
	labels = state_labels()
	return {state: labels[state] for state in STATES}
