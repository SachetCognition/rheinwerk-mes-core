"""W1-2 — the two order legs of the W0 characterisation-parity suite (TC-W1-030).

`CHAR-ORDER-ACCEPT-01` (`OrderStateValidationService.java:44-47`) and
`CHAR-ORDER-COMPLETE-01` (`:54-63`) were pinned in W0 against the fixture-encoded legacy
rule. With `rheinwerk_mes.execution_gating.contracts` in place they resolve to the target
implementation instead — the flip ADR-001 asks for — and the frozen fixtures must still
pass verbatim, with no test or fixture change.

This suite is offline (no site): the contract entrypoints are pure functions over mappings.
TC-W1-030 steps 2 and 3; URS-W1-005 and URS-W1-007 (and URS-W1-030 for the record).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

contracts = pytest.importorskip("rheinwerk_mes.execution_gating.contracts")

# The W0 harness lives in `tests/characterisation` and is imported as a top-level package
# (same convention as the W1-1 parity assertion), read-only.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from characterisation.registry import get  # noqa: E402

TARGET_MODULE = "rheinwerk_mes.execution_gating.contracts"


@pytest.mark.parametrize("contract_id", ["CHAR-ORDER-ACCEPT-01", "CHAR-ORDER-COMPLETE-01"])
def test_order_contract_resolves_to_the_target_implementation(contract_id):
	"""URS-W1-005 · URS-W1-007 · TC-W1-030 — the contract no longer runs the legacy fallback."""
	resolution = get(contract_id).resolution()
	assert resolution.source.startswith(TARGET_MODULE), (
		f"{contract_id} still runs {resolution.source}; the W1 gate must own the contract"
	)


@pytest.mark.parametrize("contract_id", ["CHAR-ORDER-ACCEPT-01", "CHAR-ORDER-COMPLETE-01"])
def test_every_frozen_case_still_passes_against_the_target(contract_id):
	"""URS-W1-005 · URS-W1-007 · TC-W1-030 steps 2+3 — frozen fixtures pass unchanged."""
	contract = get(contract_id)
	cases = contract.cases()
	assert cases, "the frozen fixture must not be empty"
	for case in cases:
		contract.check(case)


def test_acceptance_contract_keeps_the_legacy_message_key():
	"""URS-W1-005 · TC-W1-030 — one `fieldRequired` per missing field, legacy key verbatim."""
	verdict = contracts.evaluate_order_acceptance({})
	assert verdict.allowed is False
	assert verdict.errors == (contracts.FIELD_REQUIRED,) * 4


def test_completion_contract_keeps_the_legacy_message_key():
	"""URS-W1-007 · TC-W1-030 — zero output raises the legacy doneQuantity key."""
	verdict = contracts.evaluate_order_completion(
		{"date_from": "10.03.2026", "date_to": "12.03.2026", "done_quantity": 0}
	)
	assert verdict.allowed is False
	assert verdict.errors == (contracts.DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO,)


def test_completion_contract_allows_positive_output():
	"""URS-W1-007 — a complete order with recorded output passes the gate."""
	verdict = contracts.evaluate_order_completion(
		{"date_from": "10.03.2026", "date_to": "12.03.2026", "done_quantity": 500}
	)
	assert verdict.allowed is True and verdict.errors == ()


def test_acceptance_contract_refuses_an_end_date_before_the_start_date():
	"""URS-W1-005 AC-2 — `OrderStateService.checkOrderDates` half of the acceptance rule."""
	verdict = contracts.evaluate_order_acceptance(
		{
			"date_from": "15.03.2026",
			"date_to": "14.03.2026",
			"production_line": "LINE-1",
			"technology": "BOM-RW-CHM-0003-001",
		}
	)
	assert verdict.allowed is False
	assert verdict.errors == (contracts.DATES_ORDER_OVERDUE,)


def test_acceptance_contract_allows_a_complete_order():
	"""URS-W1-005 — dates in order plus line and recipe pass the gate."""
	verdict = contracts.evaluate_order_acceptance(
		{
			"date_from": "10.03.2026",
			"date_to": "12.03.2026",
			"production_line": "LINE-1",
			"technology": "BOM-RW-CHM-0003-001",
		}
	)
	assert verdict.allowed is True and verdict.errors == ()
