"""Line-schedule lifecycle: build, approve, reject (W3-2 · URS-W3-005, URS-W3-021).

The single entrypoint for every `schedule_state` change. It mirrors what W1 does for
`exec_state` (`docs/design/W1-exec-state.md`): legality first (Qcadoo `ScheduleState`
parity), then the role gate, then the capacity slot search, then the audit row — a refusal
never leaves a half-written schedule behind.

Only orders in `exec_state` Accepted enter a schedule (URS-W3-005 AC-1); the sequence is the
planner's, since W3 ships no optimiser (URS-W3-009).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.manufacturing_core import exec_state
from rheinwerk_mes.setup.roles import PLANNER

from . import capacity, norms
from .schedule_state import (
	APPROVED,
	DRAFT,
	INITIAL_STATE,
	REJECTED,
	is_legal,
	state_labels,
)
from .sequencing import sequence_line

SCHEDULE_DOCTYPE = "Line Schedule"
GATE = "schedule_state"

#: Roles allowed to approve or reject a schedule (URS-W3-023 AC-1 for the planner action).
DECIDING_ROLES: tuple[str, ...] = (PLANNER, "System Manager", "Administrator")


def schedulable_orders(production_line: str) -> list[dict[str, Any]]:
	"""Accepted production orders of a line, oldest planned start first (URS-W3-005 AC-1)."""
	return frappe.get_all(
		"Work Order",
		filters={
			"production_line": production_line,
			"exec_state": exec_state.ACCEPTED,
			"docstatus": ("<", 2),
		},
		fields=["name", "production_item", "qty", "planned_start_date", "exec_state"],
		order_by="planned_start_date asc, name asc",
		limit_page_length=0,
	)


def _order_payload(production_line: str, orders: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{
			"work_order": row["name"],
			"production_item": row["production_item"],
			"quantity": row["qty"],
			"exec_state": row.get("exec_state"),
			"norms": norms.order_norms(row["name"], production_line),
		}
		for row in orders
	]


def _resolve_orders(production_line: str, work_orders: Sequence[str] | None) -> list[dict[str, Any]]:
	if not work_orders:
		return schedulable_orders(production_line)
	rows = []
	for name in work_orders:
		row = frappe.db.get_value(
			"Work Order",
			name,
			["name", "production_item", "qty", "planned_start_date", "exec_state", "production_line"],
			as_dict=True,
		)
		if not row:
			frappe.throw(_("Produktionsauftrag {0} existiert nicht.").format(name))
		if row.exec_state != exec_state.ACCEPTED:
			frappe.throw(
				_("Nur angenommene Aufträge werden eingeplant: {0} steht im Zustand {1}.").format(
					name, _(row.exec_state or exec_state.PENDING)
				),
				title=_("Auftrag nicht planbar"),
			)
		rows.append(dict(row))
	return rows


@frappe.whitelist()
def create_schedule(
	production_line: str,
	work_orders: Sequence[str] | str | None = None,
	planned_start: datetime | str | None = None,
) -> str:
	"""Build a Draft schedule for `production_line` (URS-W3-005 AC-1).

	Realization times come from the TJ/TPZ norms (URS-W3-006) and the changeover norms of
	the line are inserted between consecutive orders (URS-W3-007).
	"""
	if isinstance(work_orders, str):
		work_orders = frappe.parse_json(work_orders)
	orders = _resolve_orders(production_line, work_orders)
	if not orders:
		frappe.throw(
			_("Für die Linie {0} liegen keine angenommenen Aufträge vor.").format(production_line),
			title=_("Kein Plan möglich"),
		)

	start = get_datetime(planned_start) if planned_start else get_datetime(orders[0]["planned_start_date"])
	sequenced = sequence_line(
		_order_payload(production_line, orders),
		start,
		changeover_norms=norms.changeover_norms(production_line),
		production_line=production_line,
	)

	schedule = frappe.new_doc(SCHEDULE_DOCTYPE)
	schedule.production_line = production_line
	schedule.planned_start = start
	schedule.schedule_state = INITIAL_STATE
	exec_states = {row["name"]: row.get("exec_state") for row in orders}
	for scheduled in sequenced:
		schedule.append(
			"entries",
			{
				"sequence": scheduled.sequence,
				"work_order": scheduled.work_order,
				"production_item": scheduled.production_item,
				"quantity": scheduled.quantity,
				"exec_state": exec_states.get(scheduled.work_order),
				"realization_min": scheduled.realization_min,
				"changeover_min": scheduled.changeover_min,
				"changeover_note": scheduled.changeover_note,
				"planned_start": scheduled.planned_start,
				"planned_end": scheduled.planned_end,
			},
		)
		for operation in scheduled.operations:
			schedule.append(
				"operations",
				{
					"sequence": operation.sequence,
					"work_order": scheduled.work_order,
					"operation": operation.operation,
					"workstation": operation.workstation,
					"quantity": operation.quantity,
					"tpz_min": operation.tpz_min,
					"tj_min_per_unit": operation.tj_min_per_unit,
					"setup_min": operation.setup_min,
					"run_min": operation.run_min,
					"duration_min": operation.duration_min,
					"planned_start": operation.planned_start,
					"planned_end": operation.planned_end,
				},
			)
	schedule.flags.ignore_permissions = True
	schedule.insert(ignore_permissions=True)
	return schedule.name


def order_realization(work_order: str) -> tuple[tuple[Any, ...], int]:
	"""Realization times of one production order from its norms (URS-W3-006 AC-1).

	Returns the per-operation realizations and the order total in whole minutes; MIX 330 +
	FILL 165 = 495 min for PO-2026-0001 on the programme fixtures.
	"""
	from .realization_time import order_realization as compute

	row = frappe.db.get_value("Work Order", work_order, ["qty", "production_line"], as_dict=True)
	if not row:
		frappe.throw(_("Produktionsauftrag {0} existiert nicht.").format(work_order))
	return compute(norms.order_norms(work_order, row.production_line), row.qty)


def _require_deciding_role() -> None:
	roles = set(frappe.get_roles())
	if roles.isdisjoint(DECIDING_ROLES):
		frappe.throw(
			_("Nur die Rolle {0} darf einen Linienplan freigeben oder ablehnen.").format(_(PLANNER)),
			frappe.PermissionError,
			title=_("Berechtigung fehlt"),
		)


def check_capacity(schedule: str) -> None:
	"""Slot-search every operation of the schedule against operative bookings (URS-W3-008)."""
	doc = frappe.get_doc(SCHEDULE_DOCTYPE, schedule)
	for operation in doc.operations:
		capacity.check_slot(
			document=doc,
			work_order=operation.work_order,
			operation=operation.operation,
			workstation=operation.workstation,
			window_start=operation.planned_start,
			window_end=operation.planned_end,
			production_line=doc.production_line,
			exclude_schedule=doc.name,
		)


def _transition(schedule: str, to_state: str, reason: str | None) -> str:
	doc = frappe.get_doc(SCHEDULE_DOCTYPE, schedule)
	from_state = doc.schedule_state
	labels = state_labels()

	if not is_legal(from_state, to_state):
		message = _("Übergang {0} → {1} ist nicht zulässig.").format(
			labels.get(from_state, from_state), labels.get(to_state, to_state)
		)
		audit.log_refusal(
			gate=GATE,
			rule=_("Planzustandsmaschine"),
			document=doc,
			from_state=from_state,
			to_state=to_state,
			detail=message,
		)
		frappe.throw(message, title=_("Übergang abgelehnt"))

	_require_deciding_role()

	if to_state == APPROVED:
		check_capacity(schedule)
		_supersede_operative(doc)

	doc.schedule_state = to_state
	doc.is_operative = 1 if to_state == APPROVED else 0
	doc.decided_by = frappe.session.user
	doc.decided_at = now_datetime()
	if reason:
		doc.decision_reason = reason
	doc.flags.rheinwerk_state_transition = True
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)

	audit.log_transition(
		gate=GATE,
		rule=_("Planzustandsmaschine"),
		document=doc,
		from_state=from_state,
		to_state=to_state,
		detail=_("Linienplan {0} für Linie {1}: {2}").format(
			doc.name, doc.production_line, labels.get(to_state, to_state)
		),
	)
	return doc.name


def _supersede_operative(doc: Any) -> None:
	"""One operative sequence per line: the previously approved schedule steps back."""
	for name in frappe.get_all(
		SCHEDULE_DOCTYPE,
		filters={
			"production_line": doc.production_line,
			"is_operative": 1,
			"name": ("!=", doc.name),
		},
		pluck="name",
		limit_page_length=0,
	):
		frappe.db.set_value(SCHEDULE_DOCTYPE, name, "is_operative", 0, update_modified=False)


@frappe.whitelist()
def approve(schedule: str, reason: str | None = None) -> str:
	"""Draft → Approved: the schedule becomes the operative sequence (URS-W3-005 AC-2)."""
	return _transition(schedule, APPROVED, reason)


@frappe.whitelist()
def reject(schedule: str, reason: str | None = None) -> str:
	"""Draft → Rejected: the schedule has no operative effect (URS-W3-005 AC-2)."""
	return _transition(schedule, REJECTED, reason)


def operative_schedule(production_line: str) -> str | None:
	"""The line's operative sequence, if a schedule is approved (URS-W3-005 AC-2)."""
	return frappe.db.get_value(
		SCHEDULE_DOCTYPE,
		{"production_line": production_line, "schedule_state": APPROVED, "is_operative": 1},
		"name",
	)


def draft_schedules(production_line: str) -> list[str]:
	"""Draft schedules of a line — the planner's work queue."""
	return frappe.get_all(
		SCHEDULE_DOCTYPE,
		filters={"production_line": production_line, "schedule_state": DRAFT},
		pluck="name",
		order_by="creation desc",
		limit_page_length=0,
	)
