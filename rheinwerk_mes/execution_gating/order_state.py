"""Legal `exec_state` transitions on the production-order anchor (URS-W1-002).

Absorbed with exact parity from Qcadoo `OrderState.canChangeTo`
(`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
OrderState.java:31-81` in `SachetCognition/Chem_mes@master`) — semantics only, no ported
code. The refusal itself mirrors the legacy state framework, which raises
`StateTransitionNotAlloweException` and reports
`states.messages.change.failure.transitionNotAllowed`
(`mes-plugins-states/.../StateChangeContextBuilderImpl.java:64`,
`newstates/StateExecutorService.java:175,201`).

The module is a pure function over state names so the parity contracts can execute it
without a Frappe site; `order_state_gating` is the thin document-facing wrapper.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

#: Custom field carrying the user-owned order workflow on the `Work Order` anchor (CDM-02).
EXEC_STATE_FIELD = "exec_state"

PENDING = "Pending"
ACCEPTED = "Accepted"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
DECLINED = "Declined"
INTERRUPTED = "Interrupted"
ABANDONED = "Abandoned"

#: The seven `exec_state` values, in the legacy enum order (glossary vocabulary is law).
ORDER_STATES: tuple[str, ...] = (
	PENDING,
	ACCEPTED,
	IN_PROGRESS,
	COMPLETED,
	DECLINED,
	INTERRUPTED,
	ABANDONED,
)

#: Qcadoo `OrderStateStringValues` value per canonical state — migration and parity traceability.
LEGACY_STATE_VALUES: Mapping[str, str] = {
	PENDING: "01pending",
	ACCEPTED: "02accepted",
	IN_PROGRESS: "03inProgress",
	COMPLETED: "04completed",
	DECLINED: "05declined",
	INTERRUPTED: "06interrupted",
	ABANDONED: "07abandoned",
}

#: `OrderState.canChangeTo` per source state; an empty target set marks a terminal state.
LEGAL_TRANSITIONS: Mapping[str, frozenset[str]] = {
	PENDING: frozenset({ACCEPTED, IN_PROGRESS, DECLINED}),
	ACCEPTED: frozenset({IN_PROGRESS, DECLINED}),
	IN_PROGRESS: frozenset({COMPLETED, INTERRUPTED, ABANDONED}),
	COMPLETED: frozenset(),
	DECLINED: frozenset(),
	INTERRUPTED: frozenset({IN_PROGRESS, ABANDONED}),
	ABANDONED: frozenset(),
}

TERMINAL_STATES: frozenset[str] = frozenset(
	state for state, targets in LEGAL_TRANSITIONS.items() if not targets
)

#: Legacy message key raised for every refused transition — the parity assertion.
TRANSITION_NOT_ALLOWED = "states.messages.change.failure.transitionNotAllowed"

#: Refusal texts (German-first, URS-W0-016). Named the rule, the states and the way out.
TRANSITION_REFUSED = (
	"Übergang {source} → {target} ist nicht zulässig. Zulässige Übergänge ab {source}: {allowed}."
)
TERMINAL_TRANSITION_REFUSED = (
	"{source} ist ein Endzustand: Übergang {source} → {target} ist nicht zulässig. "
	"Für eine erneute Ausführung ist ein neuer Fertigungsauftrag anzulegen."
)
UNKNOWN_STATE_REFUSED = "{state} ist kein gültiger exec_state. Gültige Zustände: {states}."


def _identity(text: str) -> str:
	return text


def parse_state(state: str) -> str:
	"""Return `state` when it is one of the seven `exec_state` values, else raise.

	Parity with `OrderState.parseString` (`OrderState.java:99-108`), which refuses an
	unparseable state rather than treating it as a missing one.
	"""
	if state not in LEGAL_TRANSITIONS:
		raise ValueError(f"unknown exec_state: {state!r}; expected one of {', '.join(ORDER_STATES)}")
	return state


def legal_targets(source: str) -> tuple[str, ...]:
	"""States reachable from `source`, ordered as `ORDER_STATES`."""
	targets = LEGAL_TRANSITIONS[parse_state(source)]
	return tuple(state for state in ORDER_STATES if state in targets)


def is_terminal(state: str) -> bool:
	"""True when no transition out of `state` is legal (Completed, Declined, Abandoned)."""
	return parse_state(state) in TERMINAL_STATES


def can_change_to(source: str | None, target: str) -> bool:
	"""Whether `source` → `target` is one of the legal `exec_state` transitions.

	A missing `source` is the initial assignment of the workflow (no transition yet) and is
	permitted, matching the legacy `sourceState != null && !sourceState.canChangeTo(...)`
	guard; every other pair — including `source` == `target` — is checked against
	`LEGAL_TRANSITIONS`.
	"""
	parse_state(target)
	if source is None:
		return True
	return target in LEGAL_TRANSITIONS[parse_state(source)]


def refusal_message(source: str, target: str, translate: Callable[[str], str] = _identity) -> str:
	"""Message naming the refused transition (URS-W1-002 AC-2).

	`translate` receives the message template so callers inside a Frappe request can pass
	`frappe._` and keep the translation catalogue keyed on the template, not on the
	interpolated text (URS-W0-016: no string concatenation).
	"""
	parse_state(source)
	parse_state(target)
	if is_terminal(source):
		return translate(TERMINAL_TRANSITION_REFUSED).format(source=source, target=target)
	return translate(TRANSITION_REFUSED).format(
		source=source, target=target, allowed=", ".join(legal_targets(source))
	)


def unknown_state_message(state: str, translate: Callable[[str], str] = _identity) -> str:
	"""Message for an `exec_state` value outside the canonical seven."""
	return translate(UNKNOWN_STATE_REFUSED).format(state=state, states=", ".join(ORDER_STATES))
