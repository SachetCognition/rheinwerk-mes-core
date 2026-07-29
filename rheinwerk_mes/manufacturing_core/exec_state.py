"""Production-order `exec_state` vocabulary and transition surface (W1-1 · URS-W1-001).

The anchor `Work Order` is never forked: `exec_state` is a Custom Field carrying the
Frappe Workflow installed by `rheinwerk_mes.setup.w1_exec_state`, so the planner and the
operator own order state explicitly instead of deriving it from postings.

This module owns the vocabulary (state names are the glossary terms, verbatim), the
role-gated transition table, and the single transition entrypoint used by the Desk
workflow bar, by sibling W1 children and by the acceptance suites.

Legacy baseline (semantics only, never ported): Qcadoo
`mes-plugins/mes-plugins-orders/.../orders/states/constants/OrderState.java:31-81`
(`canChangeTo`) in `SachetCognition/Chem_mes@master`; target model ADR-004 / CDM-02.

Refusal of illegal transitions written straight to the field, the `state_history` audit
row and the acceptance/completion gates are the subjects of URS-W1-002, URS-W1-003 and
URS-W1-004/005+ respectively; they layer onto this surface without changing it.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow

PENDING = "Pending"
ACCEPTED = "Accepted"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
INTERRUPTED = "Interrupted"
ABANDONED = "Abandoned"
DECLINED = "Declined"

#: Glossary vocabulary, in lifecycle order — the Select options and workflow states.
STATES: tuple[str, ...] = (
	PENDING,
	ACCEPTED,
	IN_PROGRESS,
	COMPLETED,
	INTERRUPTED,
	ABANDONED,
	DECLINED,
)

#: Every new production order starts here (Qcadoo `OrderState.PENDING`).
INITIAL_STATE = PENDING

#: Frappe Workflow carrying `exec_state` on the anchor Work Order.
WORKFLOW_NAME = "Production Order Execution"

#: Per-transition roles of the design record (`docs/design/LLD.md` §2.2): the planner
#: approves, declines and abandons; the shop floor runs the order.
APPROVER_ROLE = "MES Order Approver"
OPERATOR_ROLE = "Manufacturing User"

#: Desk action names — the labels the planner and operator press on the workflow bar.
ACCEPT = "Accept"
START = "Start"
DECLINE = "Decline"
COMPLETE = "Complete"
INTERRUPT = "Interrupt"
RESUME = "Resume"
ABANDON = "Abandon"

#: (from_state, to_state, action, role) — Qcadoo's `canChangeTo` set, one row per legal
#: transition, matching the workflow table of `docs/design/LLD.md` §2.2.
TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
	(PENDING, ACCEPTED, ACCEPT, APPROVER_ROLE),
	(PENDING, IN_PROGRESS, START, APPROVER_ROLE),
	(PENDING, DECLINED, DECLINE, APPROVER_ROLE),
	(ACCEPTED, IN_PROGRESS, START, OPERATOR_ROLE),
	(ACCEPTED, DECLINED, DECLINE, APPROVER_ROLE),
	(IN_PROGRESS, COMPLETED, COMPLETE, OPERATOR_ROLE),
	(IN_PROGRESS, INTERRUPTED, INTERRUPT, OPERATOR_ROLE),
	(IN_PROGRESS, ABANDONED, ABANDON, APPROVER_ROLE),
	(INTERRUPTED, IN_PROGRESS, RESUME, OPERATOR_ROLE),
	(INTERRUPTED, ABANDONED, ABANDON, APPROVER_ROLE),
)

#: Status-pill styles per state (design skill §"Component rules"); Frappe renders the
#: Workflow State style as the coloured indicator pill next to the order identifier.
STATE_STYLES: dict[str, str] = {
	PENDING: "Warning",
	ACCEPTED: "Info",
	IN_PROGRESS: "Primary",
	COMPLETED: "Success",
	INTERRUPTED: "Warning",
	ABANDONED: "Danger",
	DECLINED: "Danger",
}


def allowed_targets(state: str | None) -> frozenset[str]:
	"""States reachable from `state` (empty for the terminal states)."""
	return frozenset(
		to_state
		for from_state, to_state, _action, _role in TRANSITIONS
		if from_state == (state or INITIAL_STATE)
	)


def _load(work_order: Any) -> Any:
	return frappe.get_doc("Work Order", work_order) if isinstance(work_order, str) else work_order


@frappe.whitelist()
def transition(work_order: Any, action: str) -> Any:
	"""Apply the workflow `action` to a production order — the transition entrypoint.

	Delegates to `frappe.model.workflow.apply_workflow`, the same call the Desk workflow
	bar makes, so legality and the per-transition role live in the installed workflow
	rather than in a second, divergent rule set. Raises `frappe.ValidationError` when the
	action is not available from the order's current state (including for a user whose
	roles do not own it).
	"""
	doc = _load(work_order)
	if action not in {row[2] for row in TRANSITIONS}:
		frappe.throw(
			_("Unbekannte Zustandsaktion: {0}").format(action),
			title=_("Übergang abgelehnt"),
		)
	return apply_workflow(doc, action)


def set_default_exec_state(doc: Any, method: str | None = None) -> None:
	"""`Work Order.before_insert` — a newly created order is Pending (AC-1)."""
	if doc.meta.has_field("exec_state") and not doc.get("exec_state"):
		doc.exec_state = INITIAL_STATE
