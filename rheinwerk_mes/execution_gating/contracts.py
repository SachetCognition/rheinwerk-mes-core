"""Parity entrypoints for the characterisation harness (URS-W0-012 handover).

The harness resolves each contract to a named function in this module and falls back to
its fixture-encoded legacy rule while the function does not exist
(`tests/characterisation/api.py`). Entrypoints stay pure functions over plain mappings so
they run without a Frappe site, and return the Qcadoo message keys so parity remains
machine-checkable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rheinwerk_mes.execution_gating.order_state import TRANSITION_NOT_ALLOWED, can_change_to


@dataclass(frozen=True)
class Verdict:
	"""Outcome of an execution gate: `errors` holds legacy message keys, in legacy order."""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


def evaluate_order_transition(transition: Mapping[str, Any]) -> Verdict:
	"""Whether an `exec_state` transition is legal (URS-W1-002).

	Baseline: `OrderState.java:31-81` (`canChangeTo`) refused through
	`StateChangeContextBuilderImpl.java:64` / `StateExecutorService.java:175,201`, which
	report `states.messages.change.failure.transitionNotAllowed`. `source_state` may be
	null for the initial assignment of the workflow, which the legacy guard permits.
	"""
	source = transition.get("source_state")
	target = transition["target_state"]
	if can_change_to(source, target):
		return Verdict(allowed=True)
	return Verdict(allowed=False, errors=(TRANSITION_NOT_ALLOWED,))
