"""Production-order `exec_state` machine (W1-1 · URS-W1-001…URS-W1-004).

The anchor `Work Order` is never forked: `exec_state` is a Custom Field carrying a
Frappe Workflow (`rheinwerk_mes.setup.w1_exec_state`), and every state change — from
the Desk workflow bar, from `transition()` or from any server-side caller — funnels
through `validate_exec_state_change()`, which

1. refuses illegal transitions (`LEGAL_TRANSITIONS`, exact parity with Qcadoo
   `OrderState.canChangeTo`),
2. runs the ordered gate callbacks registered by other modules,
3. appends the `state_history` audit row (state, user, timestamp, reason).

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
OrderState.java:31-81` (transition set) and `orders/model/orderStateChange.xml:36-47`
plus `reasonTypeOfChangingOrderState.xml` (audit row + mandatory reason).

Public surface used by sibling W1 children (see `docs/design/W1-exec-state.md`):

* `transition(work_order, target_state, reason=None)` — the single transition entrypoint.
* `TransitionContext` — what a gate receives.
* hooks key `rheinwerk_exec_state_gates` — ordered dotted paths of gate callables.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

PENDING = "Pending"
ACCEPTED = "Accepted"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
INTERRUPTED = "Interrupted"
ABANDONED = "Abandoned"
DECLINED = "Declined"

#: Initial state of every production order (Qcadoo `OrderState.PENDING`).
INITIAL_STATE = PENDING

#: Qcadoo `OrderState.canChangeTo` (`OrderState.java:31-81`), state-for-state.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
	PENDING: frozenset({ACCEPTED, IN_PROGRESS, DECLINED}),
	ACCEPTED: frozenset({IN_PROGRESS, DECLINED}),
	IN_PROGRESS: frozenset({COMPLETED, INTERRUPTED, ABANDONED}),
	INTERRUPTED: frozenset({IN_PROGRESS, ABANDONED}),
	COMPLETED: frozenset(),
	DECLINED: frozenset(),
	ABANDONED: frozenset(),
}

STATES: tuple[str, ...] = (
	PENDING,
	ACCEPTED,
	IN_PROGRESS,
	COMPLETED,
	INTERRUPTED,
	ABANDONED,
	DECLINED,
)

#: States with no outgoing transition (`canChangeTo` returns false).
TERMINAL_STATES: frozenset[str] = frozenset(
	state for state, targets in LEGAL_TRANSITIONS.items() if not targets
)

#: Qcadoo `reasonTypeOfChangingOrderState.xml` — a reason is mandatory for these targets.
REASON_REQUIRED_STATES: frozenset[str] = frozenset({DECLINED, ABANDONED, INTERRUPTED})

GATE_HOOK = "rheinwerk_exec_state_gates"

#: Frappe Workflow carrying `exec_state` on the anchor Work Order.
WORKFLOW_NAME = "Production Order Execution"


def allowed_targets(state: str | None) -> frozenset[str]:
	"""Legal target states reachable from `state` (empty for terminal/unknown states)."""
	return LEGAL_TRANSITIONS.get(state or INITIAL_STATE, frozenset())


def is_legal(from_state: str | None, to_state: str) -> bool:
	"""True when Qcadoo's `canChangeTo` would allow `from_state` → `to_state`."""
	return to_state in allowed_targets(from_state)


@dataclass
class TransitionContext:
	"""Everything a gate callback needs to judge one transition.

	`errors` is the ordered, German-first message list a gate appends to; a gate may
	instead `frappe.throw` directly when it wants to present its own modal.
	"""

	doc: Any
	from_state: str
	to_state: str
	reason: str | None = None
	errors: list[str] = field(default_factory=list)

	def refuse(self, message: str) -> None:
		self.errors.append(message)


def _gate_callables() -> list:
	"""Gate callbacks in hook order — app order, then declaration order within an app."""
	return [frappe.get_attr(path) for path in frappe.get_hooks(GATE_HOOK) or []]


def run_gates(context: TransitionContext) -> None:
	"""Run every registered gate in order and refuse the transition if any objected."""
	for gate in _gate_callables():
		returned = gate(context)
		if isinstance(returned, Iterable) and not isinstance(returned, (str, bytes)):
			context.errors.extend(returned)
	if context.errors:
		frappe.throw(
			"<br>".join(context.errors),
			title=_("Übergang abgelehnt: {0} → {1}").format(_(context.from_state), _(context.to_state)),
		)


# --------------------------------------------------------------------------------------
# Core gates owned by this module (URS-W1-003, URS-W1-004). Registered first in hooks.py.
# --------------------------------------------------------------------------------------


def reason_gate(context: TransitionContext) -> None:
	"""Reason mandatory for Declined / Abandoned / Interrupted (URS-W1-003).

	Legacy baseline: `orders/model/reasonTypeOfChangingOrderState.xml` — Qcadoo requires a
	reason type on exactly these state changes.
	"""
	if context.to_state in REASON_REQUIRED_STATES and not (context.reason or "").strip():
		context.refuse(
			_("Für den Zustand {0} ist eine Begründung erforderlich (Auftrag {1}).").format(
				_(context.to_state), context.doc.name
			)
		)


def anchor_submit_gate(context: TransitionContext) -> None:
	"""Acceptance requires the anchor Work Order to be submitted (URS-W1-004 AC-1)."""
	if context.to_state == ACCEPTED and context.doc.docstatus == 0:
		context.refuse(
			_(
				"Auftrag {0} ist noch ein Entwurf. Der Fertigungsauftrag muss gebucht werden, "
				"bevor er angenommen werden kann."
			).format(context.doc.name)
		)


def shortfall_gate(context: TransitionContext) -> None:
	"""Completion requires produced ≥ ordered, or an explicit shortfall reason (URS-W1-004 AC-2)."""
	if context.to_state != COMPLETED:
		return
	produced = flt(context.doc.get("produced_qty"))
	ordered = flt(context.doc.get("qty"))
	if produced >= ordered:
		return
	shortfall_reason = (context.doc.get("shortfall_reason") or context.reason or "").strip()
	if not shortfall_reason:
		context.refuse(
			_(
				"Auftrag {0}: produzierte Menge {1} kg liegt unter der Auftragsmenge {2} kg. "
				"Für den Abschluss ist eine Mindermengen-Begründung erforderlich."
			).format(context.doc.name, produced, ordered)
		)
		return
	context.reason = shortfall_reason


# --------------------------------------------------------------------------------------
# Transition entrypoint and document hooks
# --------------------------------------------------------------------------------------


def _load(work_order: Any) -> Any:
	if isinstance(work_order, str):
		return frappe.get_doc("Work Order", work_order)
	return work_order


@frappe.whitelist()
def transition(work_order: Any, target_state: str, reason: str | None = None) -> Any:
	"""Move a production order to `target_state` — the single transition entrypoint.

	Validates legality (URS-W1-002), runs the registered gates (URS-W1-004 and the
	W1-2 execution gates) and writes the `state_history` row (URS-W1-003). Raises
	`frappe.ValidationError` when the transition is illegal or a gate refuses it.
	"""
	doc = _load(work_order)
	doc.flags.exec_state_reason = reason
	doc.exec_state = target_state
	if reason and doc.meta.has_field("exec_state_reason"):
		doc.exec_state_reason = reason
	doc.save()
	return doc


def set_default_exec_state(doc: Any, method: str | None = None) -> None:
	"""`Work Order.before_insert` — every new order starts in Pending (URS-W1-001 AC-1)."""
	if not doc.get("exec_state"):
		doc.exec_state = INITIAL_STATE


def validate_exec_state_change(doc: Any, method: str | None = None) -> None:
	"""`Work Order.validate` / `on_update_after_submit` — the one funnel for state changes."""
	if not doc.meta.has_field("exec_state"):
		return
	if doc.get("__islocal") or not frappe.db.exists("Work Order", doc.name):
		set_default_exec_state(doc)
		return

	from_state = frappe.db.get_value("Work Order", doc.name, "exec_state") or INITIAL_STATE
	to_state = doc.get("exec_state") or INITIAL_STATE
	if to_state == from_state:
		return

	if to_state not in LEGAL_TRANSITIONS:
		frappe.throw(
			_("Unbekannter Ausführungszustand: {0}").format(to_state),
			title=_("Übergang abgelehnt"),
		)
	if not is_legal(from_state, to_state):
		frappe.throw(
			_("Übergang {0} → {1} ist für Auftrag {2} nicht zulässig.{3}").format(
				_(from_state),
				_(to_state),
				doc.name,
				_(" {0} ist ein Endzustand.").format(_(from_state))
				if from_state in TERMINAL_STATES
				else _(" Zulässig sind: {0}.").format(
					", ".join(_(state) for state in sorted(allowed_targets(from_state)))
				),
			),
			title=_("Übergang abgelehnt"),
		)

	_assert_role_allowed(from_state, to_state)

	reason = doc.flags.get("exec_state_reason") or doc.get("exec_state_reason")
	context = TransitionContext(doc=doc, from_state=from_state, to_state=to_state, reason=reason)
	run_gates(context)
	_append_history(doc, from_state, to_state, context.reason)


def _assert_role_allowed(from_state: str, to_state: str) -> None:
	"""Role gating (URS-W1-001): the workflow row for this transition names the role."""
	roles = frappe.get_all(
		"Workflow Transition",
		filters={"parent": WORKFLOW_NAME, "state": from_state, "next_state": to_state},
		pluck="allowed",
	)
	if not roles:
		return
	if set(roles) & set(frappe.get_roles()):
		return
	frappe.throw(
		_("Der Übergang {0} → {1} ist der Rolle {2} vorbehalten.").format(
			_(from_state), _(to_state), ", ".join(sorted(roles))
		),
		frappe.PermissionError,
		title=_("Übergang abgelehnt"),
	)


def _append_history(doc: Any, from_state: str, to_state: str, reason: str | None) -> None:
	"""Write the audit row (URS-W1-003; Qcadoo `orderStateChange.xml:36-47`)."""
	doc.append(
		"state_history",
		{
			"from_state": from_state,
			"to_state": to_state,
			"changed_by": frappe.session.user,
			"changed_at": now_datetime(),
			"reason": reason or None,
		},
	)


def state_history(work_order: str) -> list[dict[str, Any]]:
	"""Audit rows of `work_order`, oldest first — convenience reader for siblings/tests."""
	doc = frappe.get_doc("Work Order", work_order)
	return [
		{
			"from_state": row.from_state,
			"to_state": row.to_state,
			"changed_by": row.changed_by,
			"changed_at": row.changed_at,
			"reason": row.reason,
		}
		for row in doc.get("state_history") or []
	]
