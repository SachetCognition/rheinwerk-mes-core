"""TC-W3-006 — line schedule lifecycle: Draft → Approved / Rejected.

Verifies **URS-W3-005** (per-line schedules of Accepted orders, approval makes the plan
operative, rejection has no operative effect, every decision audited) through **TC-W3-006**
of `docs/test/TST-W3-planning-boundary.md`.
"""

from __future__ import annotations

import pytest
from test_w3_scheduling_support import (
	CHANGEOVER_MINUTES,
	FIRST_ORDER,
	LINE,
	OPERATOR_USER,
	ORDER_MINUTES,
	SECOND_ORDER,
	as_planner,
	draft_schedule,
	entry_for,
	gate_log,
	require_norms,
	set_exec_state,
)

frappe = pytest.importorskip("frappe")
lifecycle = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.lifecycle")
schedule_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.schedule_state")


def test_schedule_of_accepted_orders_starts_as_draft(site):
	"""URS-W3-005 AC-1 / TC-W3-006 step 1 — the plan holds the Accepted orders, in Draft."""
	schedule = draft_schedule(site)
	assert schedule.schedule_state == schedule_state.DRAFT
	assert schedule.is_operative == 0
	assert schedule.production_line == LINE
	assert [row.work_order for row in schedule.entries] == [FIRST_ORDER, SECOND_ORDER]
	assert [row.sequence for row in schedule.entries] == [10, 20]
	assert entry_for(schedule, FIRST_ORDER).realization_min == ORDER_MINUTES
	assert entry_for(schedule, SECOND_ORDER).changeover_min == CHANGEOVER_MINUTES


def test_only_accepted_orders_are_schedulable(site):
	"""URS-W3-005 AC-1 / TC-W3-006 step 1 — a Pending order is refused, not silently planned."""
	require_norms(site)
	from test_w3_scheduling_support import accepted_order

	accepted_order(site, FIRST_ORDER)
	set_exec_state(site, FIRST_ORDER, "Pending")
	with pytest.raises(frappe.ValidationError):
		lifecycle.create_schedule(LINE, [FIRST_ORDER])
	assert FIRST_ORDER not in lifecycle.schedulable_orders(LINE)


def test_planner_approval_makes_the_schedule_operative(site):
	"""URS-W3-005 AC-2 / TC-W3-006 step 2 — Approved is the operative sequence of the line."""
	schedule = draft_schedule(site)
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Reihenfolge geprüft")
	schedule.reload()
	assert schedule.schedule_state == schedule_state.APPROVED
	assert schedule.is_operative == 1
	assert schedule.decided_by and schedule.decided_at
	assert lifecycle.operative_schedule(LINE) == schedule.name


def test_rejected_schedule_has_no_operative_effect(site):
	"""URS-W3-005 AC-2 / TC-W3-006 step 3 — Rejected changes nothing on the line."""
	approved = draft_schedule(site)
	as_planner(site)
	lifecycle.approve(approved.name, reason="Reihenfolge geprüft")

	rejected = draft_schedule(site, [FIRST_ORDER])
	lifecycle.reject(rejected.name, reason="Rüstfolge unwirtschaftlich")
	rejected.reload()
	assert rejected.schedule_state == schedule_state.REJECTED
	assert rejected.is_operative == 0
	assert lifecycle.operative_schedule(LINE) == approved.name


def test_approving_a_new_schedule_supersedes_the_previous_one(site):
	"""URS-W3-005 AC-2 / TC-W3-006 — a line has exactly one operative sequence."""
	first = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.approve(first.name, reason="Erstplan")

	second = draft_schedule(site, [FIRST_ORDER], planned_start="2026-03-09 06:00:00")
	lifecycle.approve(second.name, reason="Neuplanung")
	first.reload()
	assert first.is_operative == 0
	assert first.schedule_state == schedule_state.APPROVED
	assert lifecycle.operative_schedule(LINE) == second.name


def test_decisions_are_audited(site):
	"""URS-W3-005 AC-3 / TC-W3-006 step 4 — approval and rejection land in the audit trail."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Reihenfolge geprüft")
	rows = gate_log(site, lifecycle.GATE, schedule.name)
	assert rows, "no audit row for the approval"
	assert rows[0]["outcome"] == "Durchgeführt"
	assert rows[0]["from_state"] == schedule_state.DRAFT
	assert rows[0]["to_state"] == schedule_state.APPROVED

	rejected = draft_schedule(site, [FIRST_ORDER])
	lifecycle.reject(rejected.name, reason="Rüstfolge unwirtschaftlich")
	rows = gate_log(site, lifecycle.GATE, rejected.name)
	assert rows[0]["to_state"] == schedule_state.REJECTED


def test_deciding_is_reserved_for_the_planner_role(site):
	"""URS-W3-005 / TC-W3-006 — the operator may not approve a line schedule."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	if not site.db.exists("User", OPERATOR_USER):
		pytest.skip("operator persona not seeded on this site")
	site.set_user(OPERATOR_USER)
	with pytest.raises(frappe.PermissionError):
		lifecycle.approve(schedule.name)
