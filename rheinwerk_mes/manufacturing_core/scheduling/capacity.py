"""The anchor's capacity slot search, retained under the schedule layer (URS-W3-008).

Adopted from ERPNext (never forked): the work centre's ceiling is the anchor
`Workstation.production_capacity` and the refusal is raised with the anchor's own
`CapacityError` (`erpnext/manufacturing/doctype/work_order/services/operations.py:105-130`,
`work_order.py`), so every existing anchor handler for an unplaceable operation keeps
working. What W3-2 adds is the *presentation and audit*: the refusal is modal and names
rule, record and resolution (design skill §"Hard gates look hard", URS-W3-008) and lands in
the W1 `Execution Gate Log` (URS-W3-021 AC-1).

A booking is an operation of an **Approved** (operative) line schedule at the same work
centre whose window overlaps the requested one; the earliest feasible slot is the earliest
end among the blocking bookings, i.e. the moment capacity frees up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.execution_gating.gates import hard_gate_message

from .schedule_state import APPROVED

GATE = "capacity_slot_search"

#: Rule name of the refusal, stable for the audit view and the tests.
CAPACITY_RULE = "Kapazität des Arbeitsplatzes"

#: Default `production_capacity` when the anchor record leaves it empty — one job at a time.
DEFAULT_CAPACITY = 1


@dataclass(frozen=True)
class Booking:
	"""One occupied slot at a work centre."""

	work_order: str
	schedule: str
	operation: str
	planned_start: datetime
	planned_end: datetime


def capacity_error() -> type[Exception]:
	"""The anchor's `CapacityError` — imported lazily so the module loads without ERPNext."""
	from erpnext.manufacturing.doctype.work_order.work_order import CapacityError

	return CapacityError


def production_capacity(workstation: str | None) -> int:
	"""The anchor work centre's `production_capacity` (`workstation.json`)."""
	if not workstation:
		return DEFAULT_CAPACITY
	value = frappe.db.get_value("Workstation", workstation, "production_capacity")
	return int(value or DEFAULT_CAPACITY)


def bookings(
	workstation: str,
	window_start: datetime | str,
	window_end: datetime | str,
	*,
	exclude_schedule: str | None = None,
) -> list[Booking]:
	"""Operative bookings of `workstation` overlapping the requested window."""
	start = get_datetime(window_start)
	end = get_datetime(window_end)
	filters: dict[str, Any] = {
		"workstation": workstation,
		"parenttype": "Line Schedule",
	}
	rows = frappe.get_all(
		"Line Schedule Operation",
		filters=filters,
		fields=["parent", "work_order", "operation", "planned_start", "planned_end"],
		order_by="planned_end asc",
		limit_page_length=0,
	)
	operative = {
		name
		for name in frappe.get_all(
			"Line Schedule",
			filters={"schedule_state": APPROVED, "is_operative": 1},
			pluck="name",
			limit_page_length=0,
		)
	}
	occupied = []
	for row in rows:
		if row["parent"] not in operative or row["parent"] == exclude_schedule:
			continue
		booking_start = get_datetime(row["planned_start"])
		booking_end = get_datetime(row["planned_end"])
		if booking_start < end and start < booking_end:
			occupied.append(
				Booking(
					work_order=row["work_order"],
					schedule=row["parent"],
					operation=row["operation"],
					planned_start=booking_start,
					planned_end=booking_end,
				)
			)
	return occupied


def earliest_feasible_slot(occupied: Sequence[Booking]) -> datetime | None:
	"""When capacity frees up: the earliest end among the blocking bookings."""
	if not occupied:
		return None
	return min(booking.planned_end for booking in occupied)


def _de_datetime(value: datetime) -> str:
	"""DD.MM.YYYY HH:MM (URS-W3-022)."""
	return value.strftime("%d.%m.%Y %H:%M")


def check_slot(
	*,
	document: Any,
	work_order: str,
	operation: str,
	workstation: str | None,
	window_start: datetime | str,
	window_end: datetime | str,
	production_line: str | None = None,
	exclude_schedule: str | None = None,
) -> None:
	"""Refuse an operation that cannot be placed at `workstation` (URS-W3-008 AC-1).

	Raises the anchor `CapacityError` with a modal, logged rule/record/resolution refusal
	naming the work centre, the blocking booking and the earliest feasible slot.
	"""
	if not workstation:
		return
	capacity = production_capacity(workstation)
	occupied = bookings(workstation, window_start, window_end, exclude_schedule=exclude_schedule)
	if len(occupied) < capacity:
		return

	work_centre = f"{production_line}/{workstation}" if production_line else workstation
	blocking = occupied[0]
	free_at = earliest_feasible_slot(occupied)
	message = hard_gate_message(
		rule=_("{0}: Arbeitsplatz {1} ist im Planfenster mit {2} von {3} Belegungen ausgelastet.").format(
			CAPACITY_RULE, work_centre, len(occupied), capacity
		),
		record=_("Auftrag {0}, Arbeitsgang {1}; blockierende Belegung: {2} ({3}) bis {4}").format(
			work_order,
			operation,
			blocking.work_order,
			blocking.schedule,
			_de_datetime(blocking.planned_end),
		),
		resolution=_(
			"Frühester möglicher Slot: {0} — Auftrag dorthin verschieben oder Kapazität erhöhen."
		).format(_de_datetime(free_at) if free_at else _de_datetime(get_datetime(window_end))),
	)
	audit.log_refusal(
		gate=GATE,
		rule=CAPACITY_RULE,
		document=document,
		detail=frappe.utils.strip_html(message.replace("<br>", " · ")),
	)
	frappe.throw(message, capacity_error(), title=_("Kapazität nicht verfügbar: {0}").format(work_centre))
