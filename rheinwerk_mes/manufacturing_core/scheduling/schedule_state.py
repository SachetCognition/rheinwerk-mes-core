"""Line-schedule state machine `schedule_state` (W3-2 · URS-W3-005).

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
ScheduleState.java:8-24`, the `DRAFT` block whose `canChangeTo` allows exactly `APPROVED`
and `REJECTED`. URS-W3-005 AC-3 fixes the target set to those two edges: an Approved
schedule is the operative sequence for its line and is replaced by a new Draft, never
retro-rejected. The full legacy file additionally lets `APPROVED` change to `REJECTED`
(`ScheduleState.java:16-23`); that edge is a **deliberate narrowing**, measured by the
`CHAR-SCHEDULE-STATE-01` contract and recorded in `docs/design/W3-finite-capacity.md`.

The vocabulary is `schedule_state` (never the unqualified "status", ADR-004) and its labels
come from the externalized German-first glossary below (URS-W3-022). The module keeps no
Frappe import at module level so the parity contracts can execute it offline.
"""

from __future__ import annotations

DRAFT = "Draft"
APPROVED = "Approved"
REJECTED = "Rejected"

#: Entry state of every line schedule (`ScheduleState.DRAFT`).
INITIAL_STATE = DRAFT

STATES: tuple[str, ...] = (DRAFT, APPROVED, REJECTED)

#: `ScheduleState.canChangeTo` as URS-W3-005 AC-3 fixes it — Draft is the only source state.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
	DRAFT: frozenset({APPROVED, REJECTED}),
	APPROVED: frozenset(),
	REJECTED: frozenset(),
}

#: States with no outgoing edge.
TERMINAL_STATES: frozenset[str] = frozenset(
	state for state, targets in LEGAL_TRANSITIONS.items() if not targets
)

#: The one state whose schedule is the operative sequence of its production line.
OPERATIVE_STATE = APPROVED

#: Frappe Workflow carrying `schedule_state` on `Line Schedule`.
WORKFLOW_NAME = "Line Schedule Governance"

#: Workflow actions per edge (from, to) — used by the installer and the Desk workflow bar.
ACTIONS: dict[tuple[str, str], str] = {
	(DRAFT, APPROVED): "Approve Schedule",
	(DRAFT, REJECTED): "Reject Schedule",
}

#: Qcadoo message key family, kept so refusals stay comparable across the migration.
ILLEGAL_TRANSITION = "orders.schedule.state.error.illegalTransition"


def state_labels() -> dict[str, str]:
	"""German-first glossary of the schedule states (URS-W3-022 AC-1)."""
	from frappe import _

	return {
		DRAFT: _("Entwurf"),
		APPROVED: _("Freigegeben"),
		REJECTED: _("Abgelehnt"),
	}


def allowed_targets(state: str | None) -> frozenset[str]:
	"""Legal target states reachable from `state` (empty for terminal/unknown states)."""
	return LEGAL_TRANSITIONS.get(state or INITIAL_STATE, frozenset())


def is_legal(from_state: str | None, to_state: str) -> bool:
	"""True when `canChangeTo` allows `from_state` → `to_state`."""
	return to_state in allowed_targets(from_state)


def transition_pairs() -> frozenset[tuple[str, str]]:
	"""Every allowed edge as a (from, to) pair — the set URS-W3-005 AC-3 enumerates."""
	return frozenset((state, target) for state, targets in LEGAL_TRANSITIONS.items() for target in targets)
