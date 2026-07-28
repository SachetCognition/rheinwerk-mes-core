"""TC-W1-001 — `exec_state` workflow lifecycle on the anchor Work Order.

Verifies **URS-W1-001** (explicit, role-gated `exec_state` workflow layered over the
anchor Work Order, never forking it) through **TC-W1-001** of
`docs/test/TST-W1-production-core.md`.
"""

from __future__ import annotations

import pytest
from test_w1_exec_state_support import (
	OPERATOR_USER,
	PLANNER_USER,
	draft_order,
	submitted_order,
)

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")


def test_new_order_starts_pending(site):
	"""URS-W1-001 AC-1 / TC-W1-001 step 1 — a newly created order is Pending."""
	order = draft_order(site)
	assert order.exec_state == exec_state.PENDING
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.PENDING


def test_anchor_work_order_is_not_forked(site):
	"""URS-W1-001 / TC-W1-001 step 1 — `exec_state` is a Custom Field, not an anchor fork."""
	field = site.db.get_value(
		"Custom Field", {"dt": "Work Order", "fieldname": "exec_state"}, ["module", "fieldtype"]
	)
	assert field == ("Manufacturing Core", "Select")
	assert site.db.get_value("DocType", "Work Order", "module") == "Manufacturing"


def test_workflow_is_active_on_the_anchor(site):
	"""URS-W1-001 / TC-W1-001 — the workflow is installed from committed code."""
	workflow = site.get_doc("Workflow", exec_state.WORKFLOW_NAME)
	assert workflow.is_active == 1
	assert workflow.document_type == "Work Order"
	assert workflow.workflow_state_field == "exec_state"
	assert {row.state for row in workflow.states} == set(exec_state.STATES)


def test_planner_accepts_then_operator_runs_interrupts_and_resumes(site):
	"""URS-W1-001 AC-2/AC-3 / TC-W1-001 steps 2-3 — the lifecycle, per persona."""
	order = submitted_order(site)

	site.set_user(PLANNER_USER)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.ACCEPTED

	site.set_user(OPERATOR_USER)
	exec_state.transition(order.name, exec_state.IN_PROGRESS)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.IN_PROGRESS

	exec_state.transition(order.name, exec_state.INTERRUPTED, reason="Störung Mischer MIX-01")
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.INTERRUPTED

	exec_state.transition(order.name, exec_state.IN_PROGRESS)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.IN_PROGRESS


def test_accept_is_reserved_for_the_planner_role(site):
	"""URS-W1-001 (role gating) / TC-W1-001 — the operator may not accept an order."""
	order = submitted_order(site)
	site.set_user(OPERATOR_USER)
	with pytest.raises(frappe.PermissionError):
		exec_state.transition(order.name, exec_state.ACCEPTED)
