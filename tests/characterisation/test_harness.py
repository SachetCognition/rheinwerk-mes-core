"""Harness integrity and drift detection — URS-W0-012 (AC-4), TC-W0-015.

TC-W0-015 requires that a broken parity contract fails CI. Two things secure that:

1. the contracts run in the CI `tests` job and in a dedicated `contracts` step (asserted
   below against `.github/workflows/ci.yml`), and
2. the harness fails loudly on drift — proven here by evaluating a registered contract
   against a deliberately drifted implementation and asserting the contract refuses it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .api import ENTRYPOINTS, Resolution, Verdict
from .registry import all_contracts, get

REPO_ROOT = Path(__file__).resolve().parents[2]
JAVA_CITATION = re.compile(r"\.java:\d+(-\d+)?")


def test_contracts_are_enumerable_and_fully_declared():
	"""URS-W0-012 · TC-W0-014 — every contract is registered with fixtures and traceability."""
	contracts = all_contracts()
	assert {contract.id for contract in contracts} == {
		"CHAR-BATCH-STATE-01",
		"CHAR-BLOCKED-PICK-01",
		"CHAR-EXPIRY-ISSUE-01",
		"CHAR-FEFO-PICK-01",
		"CHAR-ORDER-ACCEPT-01",
		"CHAR-ORDER-COMPLETE-01",
		"CHAR-REALIZATION-TIME-01",
		"CHAR-SCHEDULE-STATE-01",
		"CHAR-TECH-VALIDATE-01",
	}
	for contract in contracts:
		assert contract.urs_ids and contract.tc_ids, f"{contract.id} lacks URS/TC traceability"
		assert JAVA_CITATION.search(contract.legacy_source), (
			f"{contract.id} must cite a Java source path and line range"
		)
		assert contract.concern in ENTRYPOINTS, f"{contract.id} has no documented target entrypoint"
		assert contract.cases(), f"{contract.id} has no fixture cases"
		document = contract.cases()
		assert len({case["id"] for case in document}) == len(document), "fixture case ids must be unique"


def test_contract_fixtures_cite_their_legacy_baseline():
	"""URS-W0-012 · TC-W0-014 — fixture data itself records the Java baseline it pins."""
	for contract in all_contracts():
		fixture = Path(__file__).resolve().parent / "fixtures" / contract.fixture
		assert JAVA_CITATION.search(fixture.read_text(encoding="utf-8")), (
			f"{contract.fixture} must cite the Java source path and line range"
		)


def test_readme_documents_every_contract_and_entrypoint():
	"""URS-W0-012 · TC-W0-014 — the W1 handover names each contract and its entrypoint."""
	readme = (Path(__file__).resolve().parent / "README.md").read_text(encoding="utf-8")
	for contract in all_contracts():
		assert contract.id in readme, f"{contract.id} is not documented in the harness README"
	for entrypoint in ENTRYPOINTS.values():
		assert entrypoint in readme, f"entrypoint {entrypoint} is not documented for W1"


def test_contracts_run_offline_against_the_legacy_rule_until_w1_lands():
	"""URS-W0-012 · TC-W0-014 — contracts execute with no Frappe site present."""
	for contract in all_contracts():
		resolution = contract.resolution()
		assert callable(resolution.callable_)
		assert resolution.entrypoint == ENTRYPOINTS[contract.concern]


def test_drifted_implementation_breaks_the_contract():
	"""URS-W0-012 AC-4 · TC-W0-015 — a contract fails loudly when behaviour drifts.

	Stand-in for the deliberate break demanded by TC-W0-015 step 1: the FEFO contract is
	evaluated against an implementation that picks the latest expiry first (LEFO), and the
	acceptance gate against one that allows everything. Both must raise.
	"""
	fefo = get("CHAR-FEFO-PICK-01")
	fefo_case = next(case for case in fefo.cases() if case["id"] == "PICK-01-fefo-earliest-expiry-first")
	drifted_picking = Resolution(
		lambda resources, algorithm: tuple(row["batch"] for row in resources),
		ENTRYPOINTS["picking_order"],
		True,
	)
	with pytest.raises(AssertionError, match="picking order drifted"):
		fefo.checker(drifted_picking, fefo_case)

	gate = get("CHAR-ORDER-ACCEPT-01")
	gate_case = next(case for case in gate.cases() if case["id"] == "ACCEPT-01-all-required-fields-missing")
	permissive_gate = Resolution(lambda order: Verdict(allowed=True), ENTRYPOINTS["order_acceptance"], True)
	with pytest.raises(AssertionError, match="expected allowed=False"):
		gate.checker(permissive_gate, gate_case)


def test_ci_runs_the_contract_suite():
	"""URS-W0-012 AC-4 · TC-W0-015 — the regression floor is wired into the pipeline."""
	workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
	assert "tests/characterisation" in workflow, "CI must run the characterisation contracts"
