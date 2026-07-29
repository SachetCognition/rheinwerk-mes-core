"""Order-transition parity contract — URS-W1-002 AC-3 · TC-W1-030 step 1.

The fixture `fixtures/order_transition.json` is the legacy truth: `canChangeTo` per source
state as Qcadoo implements it (`OrderState.java:31-81`). Every state pair is asserted
against the target implementation
(`rheinwerk_mes.execution_gating.contracts.evaluate_order_transition`), so any drift in the
transition set fails here.

The fixture and the entrypoint follow the W0 harness handover convention
(`tests/characterisation/README.md`): once `CHAR-ORDER-TRANSITION-01` is registered in the
harness registry, the same fixture runs through `api.resolve` with no change here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rheinwerk_mes.execution_gating.contracts import evaluate_order_transition
from rheinwerk_mes.execution_gating.order_state import LEGACY_STATE_VALUES, TRANSITION_NOT_ALLOWED

FIXTURE = json.loads(
	(Path(__file__).resolve().parent / "fixtures" / "order_transition.json").read_text(encoding="utf-8")
)
STATES: list[str] = FIXTURE["states"]
CASES: list[dict] = FIXTURE["cases"]

_PAIRS = [
	(case["source_state"], target, allowed)
	for case in CASES
	for allowed, targets in (
		(True, case["expected"]["allowed_targets"]),
		(False, case["expected"]["refused_targets"]),
	)
	for target in targets
]


def test_fixture_covers_every_state_pair():
	"""Each case enumerates all seven target states, so the contract is exhaustive."""
	assert set(STATES) == set(LEGACY_STATE_VALUES)
	for case in CASES:
		expected = case["expected"]
		covered = expected["allowed_targets"] + expected["refused_targets"]
		assert sorted(covered) == sorted(STATES), f"{case['id']}: incomplete target coverage"
		assert len(covered) == len(set(covered)), f"{case['id']}: duplicate target"
	assert len(_PAIRS) == len(CASES) * len(STATES)


@pytest.mark.parametrize(
	("source", "target", "expected_allowed"),
	_PAIRS,
	ids=[f"{source or 'null'}->{target}" for source, target, _ in _PAIRS],
)
def test_transition_legality_matches_legacy(source, target, expected_allowed):
	"""URS-W1-002 AC-3 · TC-W1-030 step 1 — `OrderState.java:31-81` verdict per state pair."""
	verdict = evaluate_order_transition({"source_state": source, "target_state": target})
	assert verdict.allowed is expected_allowed, f"{source} → {target}"
	expected_errors = () if expected_allowed else (TRANSITION_NOT_ALLOWED,)
	assert verdict.errors == expected_errors


def test_legacy_state_values_match_the_fixture():
	"""The Qcadoo `OrderStateStringValues` mapping is pinned for the migration map (CDM-02)."""
	for case in CASES:
		if case["source_state"] is None:
			continue
		assert LEGACY_STATE_VALUES[case["source_state"]] == case["legacy_state_value"]
