"""TC-W1-031 — per-transition role gating (workflow-state-level RBAC).

Verifies **URS-W1-029** (every `exec_state` and `gov_state` transition gated by role at the
transition level, refusals audited) through **TC-W1-031** of
`docs/test/TST-W1-production-core.md`.
"""

from __future__ import annotations

import pytest
from test_w1_shopfloor_support import (
	CLERK_USER,
	OPERATOR_USER,
	PLANNER_USER,
	SECOND_ORDER,
	require_order,
	set_exec_state,
)

frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
transitions = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.transitions")
w1_roles = pytest.importorskip("rheinwerk_mes.setup.w1_roles")
roles = pytest.importorskip("rheinwerk_mes.setup.roles")


def _pending_order(site, name=SECOND_ORDER):
	order = require_order(site, name)
	if order.docstatus == 0:
		order.flags.ignore_permissions = True
		order.submit()
		order.reload()
	return set_exec_state(site, order, exec_state.PENDING)


def test_operator_may_not_accept_and_the_refusal_is_audited(site):
	"""URS-W1-029 AC-1/AC-3 / TC-W1-031 step 1 — refused, unchanged, audited."""
	order = _pending_order(site)
	site.set_user(OPERATOR_USER)

	with pytest.raises(frappe.PermissionError):
		transitions.request_transition(order.name, exec_state.ACCEPTED)

	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.PENDING
	refusals = w1_roles.transition_refusals("Work Order", order.name)
	assert refusals, "the refused transition is recorded"
	assert (refusals[0]["from_state"], refusals[0]["to_state"]) == (
		exec_state.PENDING,
		exec_state.ACCEPTED,
	)
	assert refusals[0]["refused_by"] == OPERATOR_USER
	assert refusals[0]["refused_at"]


def test_planner_may_accept(site):
	"""URS-W1-029 AC-2 / TC-W1-031 step 2 — the planner owns acceptance."""
	order = _pending_order(site)
	site.set_user(PLANNER_USER)

	result = transitions.request_transition(order.name, exec_state.ACCEPTED)

	assert result["exec_state"] == exec_state.ACCEPTED
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.ACCEPTED


def test_operator_runs_the_order_but_never_abandons_it(site):
	"""URS-W1-029 — the matrix is per transition, not per DocType."""
	order = _pending_order(site)
	set_exec_state(site, order, exec_state.IN_PROGRESS)
	site.set_user(OPERATOR_USER)

	assert w1_roles.may_transition(exec_state.WORKFLOW_NAME, exec_state.IN_PROGRESS, exec_state.INTERRUPTED)
	with pytest.raises(frappe.PermissionError):
		transitions.request_transition(order.name, exec_state.ABANDONED, reason="Charge unbrauchbar")


def test_warehouse_clerk_may_not_accept_a_recipe(site):
	"""URS-W1-029 AC-2 / TC-W1-031 step 3 — recipe governance belongs to the technologist."""
	if not site.db.exists("Workflow", w1_roles.GOV_WORKFLOW):
		pytest.skip(f"{w1_roles.GOV_WORKFLOW} workflow not installed on this site (W1-4)")
	site.set_user(CLERK_USER)
	assert not w1_roles.may_transition(w1_roles.GOV_WORKFLOW, "Checked", "Accepted")


def test_gov_state_matrix_is_committed_even_before_the_workflow_lands():
	"""URS-W1-029 — the `gov_state` role matrix is code, applied when W1-4 installs it."""
	assert w1_roles.GOV_TRANSITION_ROLES[("Checked", "Accepted")] == (roles.TECHNOLOGIST,)
	assert roles.WAREHOUSE_CLERK not in {
		role for roles in w1_roles.GOV_TRANSITION_ROLES.values() for role in roles
	}


def test_every_exec_transition_row_names_its_roles(site):
	"""URS-W1-029 — the installed workflow carries the committed matrix, row for row."""
	for (from_state, to_state), roles in w1_roles.EXEC_TRANSITION_ROLES.items():
		installed = w1_roles.allowed_roles(exec_state.WORKFLOW_NAME, from_state, to_state)
		assert installed == set(roles), f"{from_state} → {to_state}"


def test_audit_entries_are_immutable(site):
	"""URS-W1-029 AC-3 / URS-W1-033 — the refusal audit is append-only for everyone."""
	order = _pending_order(site)
	name = w1_roles.log_transition_refusal("Work Order", order.name, exec_state.PENDING, exec_state.ACCEPTED)

	entry = site.get_doc(w1_roles.REFUSAL_LOG, name)
	entry.message = "nachträglich geändert"
	with pytest.raises(frappe.PermissionError):
		entry.save(ignore_permissions=True)
	with pytest.raises(frappe.PermissionError):
		site.delete_doc(w1_roles.REFUSAL_LOG, name, ignore_permissions=True)
