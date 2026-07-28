"""Schedule-state and realization-time contracts — CHAR-SCHEDULE-STATE-01, CHAR-REALIZATION-TIME-01.

URS-W3-005 / URS-W3-006 · TC-W3-007, TC-W3-009.
Legacy baselines (`SachetCognition/Chem_mes@master`):
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
ScheduleState.java:8-24` and `mes-plugins/mes-plugins-production-scheduling/src/main/java/
com/qcadoo/mes/productionScheduling/OrderRealizationTimeServiceImpl.java:156-186`.

`CHAR-SCHEDULE-STATE-01` carries one case the target answers **differently on purpose**:
`ScheduleState.java:16-23` still lets an APPROVED schedule become REJECTED, while URS-W3-005
AC-3 fixes the target set to exactly {Draft → Approved, Draft → Rejected} — an approved
schedule is the operative sequence of its line and is replaced by a new Draft, never
retro-rejected. That case is flagged `new_behaviour` and carries a second expectation
(`expected_target`), so the narrowing is asserted against the target while the legacy verdict
stays pinned against the fallback (same mechanism as the W2 `Quarantined` cases).

`CHAR-REALIZATION-TIME-01` is a pure arithmetic contract: ≥ 10 TJ/TPZ combinations including
the edge values qty = 1 and TPZ = 0 must come out minute-identical.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import evaluate_schedule_state_transition, realization_time
from ..registry import Contract, register


def _expected(resolution: Resolution, case: Mapping[str, Any]) -> Mapping[str, Any]:
	"""The expectation that applies to the implementation actually under test."""
	if case.get("new_behaviour") and resolution.is_target_implementation:
		return case["expected_target"]
	return case["expected"]


def _check_state_transition(resolution: Resolution, case: Mapping[str, Any]) -> None:
	verdict = resolution.callable_(case["transition"])
	expected = _expected(resolution, case)
	assert verdict.allowed is expected["allowed"], (
		f"{case['id']}: decision drifted — expected allowed={expected['allowed']}, "
		f"got {verdict.allowed} (implementation: {resolution.source})"
	)
	assert list(verdict.errors) == list(expected["errors"]), (
		f"{case['id']}: refusal keys drifted — expected {expected['errors']}, "
		f"got {list(verdict.errors)} (implementation: {resolution.source})"
	)


def _check_realization_time(resolution: Resolution, case: Mapping[str, Any]) -> None:
	minutes = resolution.callable_(case["inputs"])
	expected = _expected(resolution, case)["minutes"]
	assert minutes == expected, (
		f"{case['id']}: realization time drifted — expected {expected} min, got {minutes} min "
		f"(implementation: {resolution.source})"
	)


SCHEDULE_STATE = register(
	Contract(
		id="CHAR-SCHEDULE-STATE-01",
		title="Line schedule moves Draft → Approved / Rejected and nowhere else",
		concern="schedule_state_transition",
		legacy_source="ScheduleState.java:8-24",
		fixture="schedule_state.json",
		fallback=evaluate_schedule_state_transition,
		checker=_check_state_transition,
		urs_ids=("URS-W3-005",),
		tc_ids=("TC-W3-007",),
	)
)

REALIZATION_TIME = register(
	Contract(
		id="CHAR-REALIZATION-TIME-01",
		title="Realization time = TPZ + truncated(quantity × TJ), minute-exact",
		concern="realization_time",
		legacy_source="OrderRealizationTimeServiceImpl.java:156-186",
		fixture="realization_time.json",
		fallback=realization_time,
		checker=_check_realization_time,
		urs_ids=("URS-W3-006",),
		tc_ids=("TC-W3-009",),
	)
)
