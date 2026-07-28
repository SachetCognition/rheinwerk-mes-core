"""Genealogy parity entrypoints for the characterisation harness (W2 fan-in).

The `qa_state` machine and the picking exclusion both decide their outcome from data that
needs no site: the current state, the requested state, the reason, and the disposition of a
candidate resource. That decision is expressed here as **pure functions over plain
mappings**, so `CHAR-BATCH-STATE-01` and `CHAR-BLOCKED-PICK-01` (TC-W2-038/039) execute
against production code offline, and `qa_state.py` / `blocking.py` import the state graph
and the non-pickable set from this module rather than declaring their own copy.

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`:
`advancedGenealogy/constants/BatchState.java:31-44` (TRACKED ⇄ BLOCKED, reversible, with a
reason on the state change) and
`materialFlowResources/criteriaModifiers/ResourceCriteriaModifiers.java:59,70` (resources
whose batch is blocked for quality control are filtered out of the resource lookups).

Two Rheinwerk additions have no legacy counterpart and are therefore asserted as *new*
behaviour rather than parity (URS-W2-006 / URS-W2-010): the `Quarantined` entry state, and
the exclusion of Quarantined stock from picking.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

QUARANTINED = "Quarantined"
RELEASED = "Released"
BLOCKED = "Blocked"

STATES: tuple[str, ...] = (QUARANTINED, RELEASED, BLOCKED)

#: Every batch enters the estate quarantined (URS-W2-006 AC-1) unless its item is QC-exempt.
INITIAL_STATE = QUARANTINED

#: `BatchState.java:31-44` gives the reversible TRACKED ⇄ BLOCKED pair — read as
#: Released ⇄ Blocked here; the Quarantined entry state adds exactly two edges.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
	QUARANTINED: frozenset({RELEASED, BLOCKED}),
	RELEASED: frozenset({BLOCKED}),
	BLOCKED: frozenset({RELEASED}),
}

#: A disposition that takes stock out of use, or puts it back, must name its reason
#: (URS-W2-006 AC-3; Qcadoo carries the reason on the batch state change).
REASON_REQUIRED_STATES: frozenset[str] = frozenset({BLOCKED, RELEASED})

#: States whose stock may not be picked, reserved or consumed (URS-W2-010). Qcadoo excluded
#: blocked stock only; Quarantined is the signed-off Rheinwerk addition.
NON_PICKABLE_STATES: frozenset[str] = frozenset({BLOCKED, QUARANTINED})

#: Refusal keys. Qcadoo refuses an illegal batch state change generically; the reason
#: requirement is the estate's own key, since Plant A validates it in the form layer.
ILLEGAL_TRANSITION = "advancedGenealogy.batch.state.error.illegalTransition"
REASON_REQUIRED = "rheinwerk.genealogy.batch.state.reasonRequired"


@dataclass(frozen=True)
class Verdict:
	"""Outcome of a disposition request — the shape the harness compares."""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


def evaluate_batch_state_transition(transition: Mapping[str, Any]) -> Verdict:
	"""Decide one `qa_state` disposition request (URS-W2-006).

	`transition` carries `from_state` (null for a fresh batch), `to_state` and `reason`.
	"""
	from_state = transition.get("from_state") or INITIAL_STATE
	to_state = transition["to_state"]
	errors: list[str] = []
	if to_state not in LEGAL_TRANSITIONS.get(from_state, frozenset()):
		errors.append(ILLEGAL_TRANSITION)
	elif to_state in REASON_REQUIRED_STATES and not str(transition.get("reason") or "").strip():
		errors.append(REASON_REQUIRED)
	return Verdict(allowed=not errors, errors=tuple(errors))


def pickable_candidates(resources: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
	"""Candidate batches a picking lookup may offer, in input order (URS-W2-010).

	`resources` carry `batch` and `qa_state`; a resource without a disposition is offered —
	the rule only ever *removes* stock whose state forbids use.
	"""
	return tuple(
		str(resource["batch"])
		for resource in resources
		if resource.get("qa_state") not in NON_PICKABLE_STATES
	)
