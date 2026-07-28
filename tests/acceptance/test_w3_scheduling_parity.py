"""TC-W3-007 — Qcadoo `ScheduleState` parity: the transition set and nothing beyond it.

Verifies **URS-W3-005** (schedule lifecycle matching Qcadoo `ScheduleState` semantics
exactly, with the one narrowing recorded in `docs/design/W3-finite-capacity.md`) through
**TC-W3-007** of `docs/test/TST-W3-planning-boundary.md`. The offline half enumerates the
machine and runs the `CHAR-SCHEDULE-STATE-01` fixture; the site-backed half proves the
refusals are real on a schedule document.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from test_w3_scheduling_support import FIRST_ORDER, as_planner, draft_schedule, gate_log

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "tests"):
	if str(path) not in sys.path:
		sys.path.insert(0, str(path))

from characterisation.registry import get as get_contract  # noqa: E402

frappe = pytest.importorskip("frappe")
lifecycle = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.lifecycle")
schedule_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.schedule_state")

#: The exact target set (URS-W3-005 AC-3); Qcadoo's Approved → Rejected edge is dropped
#: on purpose — decision D-W3-2-A in `docs/design/W3-finite-capacity.md`.
TARGET_TRANSITIONS = {("Draft", "Approved"), ("Draft", "Rejected")}


def test_transition_set_is_exactly_the_specified_one():
	"""URS-W3-005 AC-3 / TC-W3-007 — no extra transitions exist in the machine (offline)."""
	assert schedule_state.transition_pairs() == TARGET_TRANSITIONS
	assert set(schedule_state.STATES) == {"Draft", "Approved", "Rejected"}
	assert schedule_state.INITIAL_STATE == "Draft"
	assert schedule_state.allowed_targets("Approved") == frozenset()
	assert schedule_state.allowed_targets("Rejected") == frozenset()


def test_parity_contract_is_registered_against_the_target():
	"""URS-W3-005 AC-3 / TC-W3-007 — the contract cites the donor and runs on our code."""
	contract = get_contract("CHAR-SCHEDULE-STATE-01")
	assert contract.legacy_source == "ScheduleState.java:8-24"
	assert contract.urs_ids == ("URS-W3-005",) and contract.tc_ids == ("TC-W3-007",)
	assert contract.resolution().is_target_implementation


def test_every_fixture_case_matches_the_target():
	"""URS-W3-005 AC-3 / TC-W3-007 — the enumerated donor cases decide identically (offline)."""
	contract = get_contract("CHAR-SCHEDULE-STATE-01")
	cases = contract.cases()
	assert len(cases) >= 8, "the donor enumeration must cover every state pair"
	for case in cases:
		contract.check(case)


def test_illegal_transitions_are_refused_and_audited(site):
	"""URS-W3-005 AC-3 / TC-W3-007 — an approved plan is neither re-opened nor retro-rejected."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Reihenfolge geprüft")

	with pytest.raises(frappe.ValidationError):
		lifecycle.reject(schedule.name, reason="zu spät")
	refusals = [row for row in gate_log(site, lifecycle.GATE, schedule.name) if row["outcome"] == "Abgelehnt"]
	assert refusals, "the refused transition was not audited"
	assert refusals[0]["to_state"] == schedule_state.REJECTED

	schedule.reload()
	assert schedule.schedule_state == schedule_state.APPROVED


def test_state_cannot_be_written_around_the_machine(site):
	"""URS-W3-005 AC-3 / TC-W3-007 — a direct save cannot move `schedule_state`."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	schedule.schedule_state = schedule_state.APPROVED
	with pytest.raises(frappe.ValidationError):
		schedule.save(ignore_permissions=True)


def test_rejected_schedule_is_terminal(site):
	"""URS-W3-005 AC-3 / TC-W3-007 — Rejected accepts no further transition."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.reject(schedule.name, reason="Rüstfolge unwirtschaftlich")
	with pytest.raises(frappe.ValidationError):
		lifecycle.approve(schedule.name)
	schedule.reload()
	assert schedule.schedule_state == schedule_state.REJECTED
