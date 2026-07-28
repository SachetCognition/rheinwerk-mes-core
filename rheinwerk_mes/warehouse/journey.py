"""Shared journey state machine for the warehouse-completion DocTypes (W2-8).

The stocktaking and repacking journeys are both small state machines. Rather than invent a
third state-machine style, they reuse the shape established by the production-order
`exec_state` machine (`docs/design/W1-exec-state.md`): an explicit `LEGAL_TRANSITIONS`
table (exact parity with the Qcadoo `canChangeTo` enum), a single funnel that every save
passes through, role gating read from the DocType's Frappe Workflow, and a mandatory
reason for the states that require one. The one deviation from `exec_state` is that these
are new `rheinwerk_mes` DocTypes (not the anchor Work Order), so the funnel lives in the
controller `validate` and reads the *stored* state straight from the row.

Legacy baselines (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`materialFlowResources/states/constants/StocktakingState.java` and `RepackingState.java`
— both are `StateEnum` implementations whose `canChangeTo` defines the legal transitions.
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import now_datetime

#: Shared state vocabulary. Qcadoo's terminal FINALIZED/FINISHED pair (stocktaking) is
#: collapsed onto a single ACCEPTED per URS-W2-026, which names the workflow
#: draft → in progress → accepted (see `docs/design/W2-warehouse-completion.md`).
DRAFT = "Draft"
IN_PROGRESS = "In Progress"
ACCEPTED = "Accepted"
REJECTED = "Rejected"


@dataclass(frozen=True)
class Journey:
	"""A journey's transition table plus the workflow that carries it.

	`transitions` maps each state to the set of states reachable from it (a terminal
	state maps to an empty set); `reason_required` names the target states that demand a
	non-empty reason; `workflow_name` is the Frappe Workflow whose transition rows hold
	the allowed role per edge, read exactly as `exec_state` does.
	"""

	workflow_name: str
	state_field: str
	transitions: dict[str, frozenset[str]]
	initial: str
	reason_required: frozenset[str]

	def allowed_targets(self, state: str | None) -> frozenset[str]:
		return self.transitions.get(state or self.initial, frozenset())

	def is_legal(self, from_state: str | None, to_state: str) -> bool:
		return to_state in self.allowed_targets(from_state)

	@property
	def terminal_states(self) -> frozenset[str]:
		return frozenset(state for state, targets in self.transitions.items() if not targets)


def _assert_role_allowed(journey: Journey, from_state: str, to_state: str) -> None:
	"""Role gating (URS-W2-026): the workflow row for this edge names the allowed role.

	Identical mechanism to `exec_state._assert_role_allowed` — the role lives on the
	Frappe Workflow, never hard-coded in the machine, so a single installer owns it.
	"""
	roles = frappe.get_all(
		"Workflow Transition",
		filters={"parent": journey.workflow_name, "state": from_state, "next_state": to_state},
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


def set_initial_state(doc, journey: Journey) -> None:
	"""`before_insert` — every journey starts in its initial state."""
	if not doc.get(journey.state_field):
		doc.set(journey.state_field, journey.initial)


def stored_state(doc, journey: Journey) -> str:
	"""State currently persisted for `doc` (its initial state while still new)."""
	if doc.get("__islocal") or not frappe.db.exists(doc.doctype, doc.name):
		return journey.initial
	return frappe.db.get_value(doc.doctype, doc.name, journey.state_field) or journey.initial


def validate_transition(doc, journey: Journey) -> tuple[str, str] | None:
	"""The one funnel every save passes through; returns `(from, to)` when state changed.

	Refuses (in order) an unknown target, an illegal transition — naming the legal
	targets or flagging a terminal state, a mutation of an immutable terminal record, a
	transition the user's role may not make, and a reason-required target with no reason.
	The caller (the controller) runs the state's side effects only for the returned edge.
	"""
	from_state = stored_state(doc, journey)
	to_state = doc.get(journey.state_field) or journey.initial

	# A record already in a terminal state is immutable (URS-W2-026 AC-1: an accepted
	# stocktaking "becomes immutable"). No field may change once it is final.
	if from_state in journey.terminal_states:
		if doc.get("__islocal") or not frappe.db.exists(doc.doctype, doc.name):
			pass
		elif _has_pending_changes(doc):
			frappe.throw(
				_("{0} {1} ist im Zustand {2} unveränderlich.").format(
					_(doc.doctype), doc.name, _(from_state)
				),
				title=_("Änderung abgelehnt"),
			)

	if to_state == from_state:
		return None

	if to_state not in journey.transitions:
		frappe.throw(_("Unbekannter Zustand: {0}").format(to_state), title=_("Übergang abgelehnt"))
	if not journey.is_legal(from_state, to_state):
		hint = (
			_(" {0} ist ein Endzustand.").format(_(from_state))
			if from_state in journey.terminal_states
			else _(" Zulässig sind: {0}.").format(
				", ".join(_(state) for state in sorted(journey.allowed_targets(from_state)))
			)
		)
		frappe.throw(
			_("Übergang {0} → {1} ist für {2} nicht zulässig.{3}").format(
				_(from_state), _(to_state), doc.name, hint
			),
			title=_("Übergang abgelehnt"),
		)

	_assert_role_allowed(journey, from_state, to_state)

	if to_state in journey.reason_required and not (doc.get("reason") or "").strip():
		frappe.throw(
			_("Für den Zustand {0} ist eine Begründung erforderlich.").format(_(to_state)),
			title=_("Übergang abgelehnt"),
		)

	return from_state, to_state


def _has_pending_changes(doc) -> bool:
	"""True when a save of an already-terminal record would alter a stored value."""
	before = doc.get_doc_before_save()
	if before is None:
		before = frappe.get_doc(doc.doctype, doc.name)
	return doc.as_dict() != before.as_dict()


def append_history(doc, from_state: str, to_state: str, reason: str | None) -> None:
	"""Append the audit row (mirrors `exec_state.state_history`)."""
	if not doc.meta.has_field("state_history"):
		return
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


@frappe.whitelist()
def transition(doctype: str, name: str, target_state: str, reason: str | None = None):
	"""Desk/console entrypoint: move `name` to `target_state`, funnelling through validate."""
	doc = frappe.get_doc(doctype, name)
	if reason and doc.meta.has_field("reason"):
		doc.reason = reason
	doc.set(_state_field_of(doc), target_state)
	doc.save()
	return doc


def _state_field_of(doc) -> str:
	from rheinwerk_mes.warehouse import repacking, stocktaking

	return {
		"Stocktaking": stocktaking.JOURNEY.state_field,
		"Repacking": repacking.JOURNEY.state_field,
	}.get(doc.doctype, "state")
