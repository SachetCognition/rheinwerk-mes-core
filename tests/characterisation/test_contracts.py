"""Executable Qcadoo parity contracts — URS-W0-012 (AC-1…AC-3), TC-W0-014.

Every registered contract is executed against every committed fixture case. The three
TC-W0-014 steps additionally have named tests so the traceability is readable without
resolving parametrisation ids:

* step 1 — acceptance gate refusal (`OrderStateValidationService.java:44-47`)
* step 2 — completion gate refusal (`OrderStateValidationService.java:54-63`)
* step 3 — FEFO picking order (`ResourceManagementServiceImpl.java:1015-1027`)
"""

from __future__ import annotations

import pytest

from .registry import all_contracts, get

_CASES = [(contract, case) for contract in all_contracts() for case in contract.cases()]


@pytest.mark.parametrize(
	("contract", "case"),
	_CASES,
	ids=[f"{contract.id}::{case['id']}" for contract, case in _CASES],
)
def test_parity_contract(contract, case):
	"""URS-W0-012 · TC-W0-014 — the registered contract still matches the legacy verdict."""
	contract.check(case)


def _case(contract_id: str, case_id: str):
	contract = get(contract_id)
	for case in contract.cases():
		if case["id"] == case_id:
			return contract, case
	raise AssertionError(f"fixture case {case_id} missing from {contract_id}")


def test_acceptance_gate_refuses_order_without_dates_line_and_technology():
	"""URS-W0-012 AC-1 · TC-W0-014 step 1 — `OrderStateValidationService.java:44-47`."""
	contract, case = _case("CHAR-ORDER-ACCEPT-01", "ACCEPT-01-all-required-fields-missing")
	contract.check(case)
	verdict = contract.resolution().callable_(case["order"])
	assert verdict.allowed is False
	assert len(verdict.errors) == 4, "one refusal per missing required field"


def test_completion_gate_refuses_zero_done_quantity():
	"""URS-W0-012 AC-2 · TC-W0-014 step 2 — `OrderStateValidationService.java:54-63`."""
	contract, case = _case("CHAR-ORDER-COMPLETE-01", "COMPLETE-01-done-quantity-zero")
	contract.check(case)
	verdict = contract.resolution().callable_(case["order"])
	assert verdict.allowed is False
	assert "orders.order.orderStates.doneQuantityMustBeGreaterThanZero" in verdict.errors


def test_fefo_picks_earliest_expiry_batch_first():
	"""URS-W0-012 AC-3 · TC-W0-014 step 3 — `ResourceManagementServiceImpl.java:1015-1027`.

	BATCH-A-0002 (expiry 30.06.2026) is picked before BATCH-A-0001 (31.12.2026).
	"""
	contract, case = _case("CHAR-FEFO-PICK-01", "PICK-01-fefo-earliest-expiry-first")
	contract.check(case)
	picked = contract.resolution().callable_(case["resources"], "FEFO")
	assert picked == ("BATCH-A-0002", "BATCH-A-0001")


def test_technology_validator_refusal_fixtures_are_encoded_for_w1():
	"""URS-W0-012 · TC-W0-014 — `TechnologyValidationService.java:91-707` refusal fixtures.

	W0 encodes the structural refusals (empty tree, unfilled input quantities, unit
	mismatches, technology in use); W1 consumes them when the real validators land.
	"""
	contract = get("CHAR-TECH-VALIDATE-01")
	refusals = [case for case in contract.cases() if not case["expected"]["allowed"]]
	assert len(refusals) >= 4, "the four structural validator families must be encoded"
	expected_keys = {
		"technologies.technology.validate.global.error.emptyTechnologyTree",
		"technologies.technology.validate.global.error.inComponentsQuantitiesNotFilled",
		"technologies.operationDetails.validate.error.OutputUnitsNotMatch",
		"technologies.operationDetails.validate.error.UnitsNotMatch",
		"technologies.technology.state.error.orderInProgress",
	}
	encoded = {error for case in refusals for error in case["expected"]["errors"]}
	assert expected_keys <= encoded
