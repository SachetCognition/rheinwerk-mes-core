"""Batch-state and picking-exclusion contracts — CHAR-BATCH-STATE-01, CHAR-BLOCKED-PICK-01.

URS-W2-006 / URS-W2-010 · TC-W2-038, TC-W2-039.
Legacy baselines (`SachetCognition/Chem_mes@master`):
`mes-plugins/mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/advancedGenealogy/
constants/BatchState.java:31-44` and `mes-plugins/mes-plugins-material-flow-resources/src/
main/java/com/qcadoo/mes/materialFlowResources/criteriaModifiers/
ResourceCriteriaModifiers.java:59,70`.

Both contracts carry fixture cases the legacy estate has **no counterpart for** — the
`Quarantined` entry state and its exclusion from picking. Those cases are flagged
`new_behaviour` and carry a second expectation (`expected_target`), so the contract asserts
the *new* behaviour against the target while still pinning the legacy verdict against the
fallback. That keeps the addition measurable instead of leaving it as prose in the deviation
table of TST-W2 §4.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import evaluate_batch_state_transition, pickable_candidates
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


def _check_candidates(resolution: Resolution, case: Mapping[str, Any]) -> None:
	candidates = tuple(resolution.callable_(case["resources"]))
	expected = tuple(_expected(resolution, case)["candidates"])
	assert candidates == expected, (
		f"{case['id']}: candidate set drifted — expected {expected}, got {candidates} "
		f"(implementation: {resolution.source})"
	)


BATCH_STATE = register(
	Contract(
		id="CHAR-BATCH-STATE-01",
		title="Blocked ⇄ Released is reversible and each disposition names its reason",
		concern="batch_state_transition",
		legacy_source="BatchState.java:31-44",
		fixture="batch_state.json",
		fallback=evaluate_batch_state_transition,
		checker=_check_state_transition,
		urs_ids=("URS-W2-006",),
		tc_ids=("TC-W2-038",),
	)
)

BLOCKED_PICKING = register(
	Contract(
		id="CHAR-BLOCKED-PICK-01",
		title="Stock of a quality-blocked batch never reaches a picking candidate list",
		concern="pickable_candidates",
		legacy_source="ResourceCriteriaModifiers.java:59,70",
		fixture="blocked_picking.json",
		fallback=pickable_candidates,
		checker=_check_candidates,
		urs_ids=("URS-W2-010",),
		tc_ids=("TC-W2-039",),
	)
)
