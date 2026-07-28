"""Scheduling parity entrypoints for the W0-6 characterisation harness (W3-2).

This module owns the two handover entrypoints the harness lists for W3
(`tests/characterisation/api.py`): `schedule_state_transition` and `realization_time`. With
them in place `CHAR-SCHEDULE-STATE-01` and `CHAR-REALIZATION-TIME-01` stop running against
the fixture-encoded legacy rules and execute production code with the same fixtures.

Both entrypoints are **pure functions over plain mappings** (no Frappe site, no site
schema) and return the *legacy Qcadoo message keys* so parity stays machine-checkable; the
German-first planner messages are built in `lifecycle.py`.

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
ScheduleState.java:8-24` and `mes-plugins/mes-plugins-production-scheduling/src/main/java/
com/qcadoo/mes/productionScheduling/OrderRealizationTimeServiceImpl.java:156-186`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .realization_time import realization_time as _realization_time
from .schedule_state import ILLEGAL_TRANSITION, is_legal


@dataclass(frozen=True)
class Verdict:
	"""Outcome of a schedule-state evaluation — the shape the harness compares."""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


def evaluate_schedule_state_transition(transition: Mapping[str, Any]) -> Verdict:
	"""Judge one `schedule_state` edge (`ScheduleState.canChangeTo`, :8-24).

	URS-W3-005 AC-3: the target allows exactly Draft → Approved and Draft → Rejected.
	"""
	from_state = transition.get("from_state")
	to_state = transition.get("to_state")
	if not is_legal(from_state, str(to_state)):
		return Verdict(allowed=False, errors=(ILLEGAL_TRANSITION,))
	return Verdict(allowed=True)


def realization_time(inputs: Mapping[str, Any]) -> int:
	"""Whole minutes of realization time for one operation or a routed order (URS-W3-006)."""
	return _realization_time(inputs)
