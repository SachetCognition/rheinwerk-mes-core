"""TC-W1-038 — the two W1 exit journeys in one run (planner, then operator).

Verifies **URS-W1-001** (production-order lifecycle over the anchor Work Order) and
**URS-W1-026** (operator job-card execution) end to end, with the URS-W1-005…008 gates in
the loop, exactly as step 1…4 of TC-W1-038 in `docs/test/TST-W1-production-core.md`
prescribe: P. Krüger plans, accepts and starts PO-2026-0001 (500 kg on LINE-1,
10.03.–12.03.2026, Accepted recipe); O. Weber identifies the order by scanner, runs MIX and
FILL with one pause/resume, records 500 kg and completes the order; B. Vogel then reads the
completed order and its audit trail.

Every step is the production entrypoint a persona would trigger from the screens — no gate
is bypassed, and nothing is forced into place except the arrangement of the seeded order
before the journey starts.
"""

from __future__ import annotations

import pytest
from test_w1_gating_support import LINE, RECIPE, set_governance_state
from test_w1_shopfloor_support import (
	FILL,
	FIRST_ORDER,
	MIX,
	OPERATOR_USER,
	PLANNER_USER,
	VIEWER_USER,
	job_card,
	require_order,
)

frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
transitions = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.transitions")
job_execution = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.job_execution")
scanner = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.scanner")

QUANTITY = 500.0
POSTING_DATE = "2026-03-12"


def book_production(site, order, qty: float = QUANTITY):
	"""Post the Manufacture entry that turns recorded operation output into `produced_qty`.

	The booking runs through the anchor's own routine (`work_order.make_stock_entry`), so the
	journey exercises the real posting path — expiry policy, reservations and anchor
	validation included — rather than writing `produced_qty` by hand.

	Stock posting rights are the substrate's (`Stock User`/`Stock Manager`); the W1 role model
	grants none of the three programme roles submit access to Stock Entry (`setup/roles.py`),
	so this step runs as the stock user the plant would use. The persona-owned acts — the
	state transitions and the job-card bookings — stay with P. Krüger and O. Weber.
	"""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	current_user = site.session.user
	site.set_user("Administrator")

	entry = site.get_doc(make_stock_entry(order.name, "Manufacture", qty))
	entry.posting_date = POSTING_DATE
	entry.posting_time = "14:00:00"
	entry.set_posting_time = 1
	entry.flags.ignore_permissions = True
	entry.save()
	entry.submit()
	site.set_user(current_user)
	order.reload()
	return entry


@pytest.fixture
def planned_order(site):
	"""PO-2026-0001 as the planner leaves it: submitted, Pending, Accepted recipe, no history."""
	order = require_order(site, FIRST_ORDER)
	set_governance_state(site, RECIPE, "Accepted")
	if order.docstatus == 0:
		if not order.get("operations"):
			order.set_work_order_operations()
		order.flags.ignore_permissions = True
		order.save()
		order.submit()
		order.reload()
	site.db.set_value(
		"Work Order",
		order.name,
		{
			"exec_state": exec_state.INITIAL_STATE,
			"planned_start_date": "2026-03-10 06:00:00",
			"planned_end_date": "2026-03-12 14:00:00",
			"production_line": LINE,
		},
		update_modified=False,
	)
	site.db.delete("Order State History", {"parent": order.name})
	order.reload()
	return order


def test_planner_accepts_and_starts_the_order(site, planned_order):
	"""URS-W1-001 · TC-W1-038 steps 1+2 — the planner's journey passes every gate."""
	site.set_user(PLANNER_USER)

	accepted = transitions.request_transition(planned_order.name, exec_state.ACCEPTED)
	assert accepted["exec_state"] == exec_state.ACCEPTED

	started = transitions.request_transition(planned_order.name, exec_state.IN_PROGRESS)
	assert started["exec_state"] == exec_state.IN_PROGRESS
	assert started["from_state"] == exec_state.ACCEPTED


def test_operator_runs_both_operations_and_completes_the_order(site, planned_order):
	"""URS-W1-026 · TC-W1-038 steps 3+4 — scanner, pause/resume, 500 kg, Completed."""
	site.set_user(PLANNER_USER)
	transitions.request_transition(planned_order.name, exec_state.ACCEPTED)
	transitions.request_transition(planned_order.name, exec_state.IN_PROGRESS)

	site.set_user(OPERATOR_USER)
	scanned = scanner.scan(planned_order.name)
	assert scanned["recognised"] is True and scanned["kind"] == "work_order"

	queue = job_execution.job_queue(planned_order.name)
	assert [job["operation"] for job in queue["jobs"]] == [MIX, FILL]

	mix = job_card(site, planned_order, MIX)
	job_execution.start_job(mix.name)
	paused = job_execution.pause_job(mix.name)
	assert paused["job_status"] == "On Hold"
	resumed = job_execution.resume_job(mix.name)
	assert resumed["job_status"] == "Work In Progress"
	job_execution.record_output(mix.name, QUANTITY, submit=True)

	fill = job_card(site, planned_order, FILL)
	job_execution.start_job(fill.name)
	booked = job_execution.record_output(fill.name, QUANTITY, submit=True)
	assert booked["total_completed_qty"] == QUANTITY

	book_production(site, planned_order)
	assert site.db.get_value("Work Order", planned_order.name, "produced_qty") == QUANTITY

	completed = transitions.request_transition(planned_order.name, exec_state.COMPLETED)
	assert completed["exec_state"] == exec_state.COMPLETED


def test_state_history_is_complete_and_readable_by_the_viewer(site, planned_order):
	"""URS-W1-001 · TC-W1-038 step 4 — B. Vogel sees the order and its full audit trail."""
	site.set_user(PLANNER_USER)
	transitions.request_transition(planned_order.name, exec_state.ACCEPTED)
	transitions.request_transition(planned_order.name, exec_state.IN_PROGRESS)

	site.set_user(OPERATOR_USER)
	mix = job_card(site, planned_order, MIX)
	job_execution.start_job(mix.name)
	job_execution.record_output(mix.name, QUANTITY, submit=True)
	fill = job_card(site, planned_order, FILL)
	job_execution.start_job(fill.name)
	job_execution.record_output(fill.name, QUANTITY, submit=True)
	book_production(site, planned_order)
	transitions.request_transition(planned_order.name, exec_state.COMPLETED)

	site.set_user(VIEWER_USER)
	history = exec_state.state_history(planned_order.name)

	assert [(row["from_state"], row["to_state"]) for row in history] == [
		(exec_state.PENDING, exec_state.ACCEPTED),
		(exec_state.ACCEPTED, exec_state.IN_PROGRESS),
		(exec_state.IN_PROGRESS, exec_state.COMPLETED),
	]
	assert [row["changed_by"] for row in history] == [PLANNER_USER, PLANNER_USER, OPERATOR_USER]
	assert all(row["changed_at"] for row in history), "every audit row is timestamped"
	assert frappe.db.get_value("Work Order", planned_order.name, "exec_state") == exec_state.COMPLETED
