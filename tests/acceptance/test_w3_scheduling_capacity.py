"""TC-W3-011 — the anchor's capacity slot search, retained and made modal-grade.

Verifies **URS-W3-008** (an unplaceable operation is refused with a capacity gate refusal
naming the work centre, the blocking booking and the earliest feasible slot, and the refusal
is audited) through **TC-W3-011** of `docs/test/TST-W3-planning-boundary.md`.
"""

from __future__ import annotations

import pytest
from test_w3_scheduling_support import (
	FIRST_ORDER,
	LINE,
	MIX_WORK_CENTRE,
	PLAN_START,
	SECOND_ORDER,
	as_planner,
	draft_schedule,
	gate_log,
)

frappe = pytest.importorskip("frappe")
capacity = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.capacity")
lifecycle = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.lifecycle")


def _occupied_line(site):
	"""An approved schedule whose MIX-01 booking occupies the plan window."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Erstplan")
	return schedule


def test_work_centre_capacity_comes_from_the_anchor(site):
	"""URS-W3-008 / TC-W3-011 — the ceiling is `Workstation.production_capacity`, not a fork."""
	assert site.db.exists("Workstation", MIX_WORK_CENTRE)
	assert capacity.production_capacity(MIX_WORK_CENTRE) >= 1
	assert site.db.get_value("DocType", "Workstation", "module") == "Manufacturing"


def test_unplaceable_operation_is_refused_with_the_anchor_error(site):
	"""URS-W3-008 AC-1 / TC-W3-011 step 1 — approval is refused with ERPNext `CapacityError`."""
	_occupied_line(site)
	clash = draft_schedule(site, [SECOND_ORDER], planned_start=PLAN_START)
	with pytest.raises(capacity.capacity_error()) as refusal:
		lifecycle.approve(clash.name, reason="Parallelplan")

	message = str(refusal.value)
	assert MIX_WORK_CENTRE in message and LINE in message
	assert FIRST_ORDER in message, "the blocking booking is not named"
	assert "Regel" in message and "Datensatz" in message and "Behebung" in message
	assert "Frühester möglicher Slot" in message

	clash.reload()
	assert clash.schedule_state == "Draft"
	assert clash.is_operative == 0


def test_refusal_is_audited_as_a_capacity_gate_record(site):
	"""URS-W3-008 AC-2 / TC-W3-011 step 2 — the refusal is a record, not only a message."""
	_occupied_line(site)
	clash = draft_schedule(site, [SECOND_ORDER], planned_start=PLAN_START)
	with pytest.raises(capacity.capacity_error()):
		lifecycle.approve(clash.name, reason="Parallelplan")

	rows = gate_log(site, capacity.GATE, clash.name)
	assert rows, "no audit row for the capacity refusal"
	assert rows[0]["outcome"] == "Abgelehnt"
	assert rows[0]["rule"] == capacity.CAPACITY_RULE
	assert MIX_WORK_CENTRE in rows[0]["detail"]
	assert "<br>" not in rows[0]["detail"]


def test_free_window_is_placed_without_a_refusal(site):
	"""URS-W3-008 AC-1 / TC-W3-011 step 3 — after the blocking booking ends, the plan passes."""
	_occupied_line(site)
	later = draft_schedule(site, [SECOND_ORDER], planned_start="2026-03-05 06:00:00")
	lifecycle.approve(later.name, reason="Folgeplan")
	later.reload()
	assert later.schedule_state == "Approved"


def test_earliest_feasible_slot_is_the_first_free_moment():
	"""URS-W3-008 AC-1 / TC-W3-011 — the resolution names when capacity frees up (offline)."""
	from datetime import datetime

	bookings = (
		capacity.Booking(
			work_order=FIRST_ORDER,
			schedule="LS-LINE-1-00001",
			operation="MIX",
			planned_start=datetime(2026, 3, 2, 6, 0),
			planned_end=datetime(2026, 3, 2, 11, 30),
		),
		capacity.Booking(
			work_order=SECOND_ORDER,
			schedule="LS-LINE-1-00002",
			operation="MIX",
			planned_start=datetime(2026, 3, 2, 7, 0),
			planned_end=datetime(2026, 3, 2, 9, 0),
		),
	)
	assert capacity.earliest_feasible_slot(bookings) == datetime(2026, 3, 2, 9, 0)
	assert capacity.earliest_feasible_slot(()) is None
