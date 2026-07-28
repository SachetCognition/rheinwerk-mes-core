"""W1-4 — structural validators at Checked→Accepted, and their Qcadoo parity.

TC-W1-016 (URS-W1-015): UoM consistency, tree/BOM completeness, unit declaration, stored
validator results.
TC-W1-030 step 4 / `CHAR-TECH-VALIDATE-01` (URS-W1-015): the parity contract now resolves
to `rheinwerk_mes.manufacturing_core.contracts.evaluate_technology`, i.e. to production
code, rather than to the fixture-encoded legacy rule.

Qcadoo baseline for the whole battery: `TechnologyValidationService.java:91-707`.
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.manufacturing_core.contracts")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")
validators = pytest.importorskip("rheinwerk_mes.recipe_isa88.validators")

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"


def _successor_bom(site, mutate=None) -> str:
	"""A second anchor BOM version for the compound, optionally mutated before insert."""
	successor = site.copy_doc(site.get_doc("BOM", BOM_NAME))
	successor.is_default = 0
	successor.is_active = 1
	if mutate:
		mutate(successor)
	successor.insert()
	return successor.name


def _draft_governance(site, bom: str):
	return site.get_doc({"doctype": "Recipe Governance", "bom": bom, "routing": ROUTING}).insert()


# ------------------------------------------------------------------ TC-W1-016, site-backed


def test_tc_w1_016_uom_mismatch_on_a_component_line_refuses_acceptance(site):
	"""TC-W1-016 step 1 (URS-W1-015 AC-1): a RW-CHM-0002 line measured in a unit with no
	item-level conversion refuses acceptance, and the refusal names the offending line."""

	def break_uom(bom):
		row = next(row for row in bom.items if row.item_code == "RW-CHM-0002")
		row.uom = "Nos"
		row.conversion_factor = 1

	broken = _successor_bom(site, break_uom)
	doc = _draft_governance(site, broken)

	with pytest.raises(site.exceptions.ValidationError) as refusal:
		governance.transition(doc, governance.ACCEPTED)
	message = str(refusal.value)
	assert "RW-CHM-0002" in message
	assert "Nos" in message

	doc.reload()
	assert doc.gov_state == governance.DRAFT
	failed = {row.validator for row in doc.validator_results if not row.passed}
	assert failed == {"component_unit_convertible"}


def test_tc_w1_016_validator_results_are_stored_on_the_governance_record(site):
	"""TC-W1-016 step 4 (URS-W1-015 AC-3): a successful acceptance stores the full battery
	with its verdicts, the validating user and the timestamp."""
	successor = _successor_bom(site)
	doc = _draft_governance(site, successor)
	governance.transition(doc, governance.CHECKED)

	assert [row.validator for row in doc.validator_results] == list(validators.VALIDATORS)
	assert all(row.passed for row in doc.validator_results)
	assert doc.validated_by == site.session.user
	assert doc.validated_on


def test_tc_w1_016_component_less_recipe_fails_the_completeness_validator(site):
	"""TC-W1-016 step 2/3 (URS-W1-015 AC-2): a recipe whose operations have no input
	components fails tree completeness. The anchor refuses to submit a component-less BOM
	at all, so completeness is asserted on the snapshot the governance record validates."""
	snapshot = governance.recipe_snapshot(BOM_NAME, ROUTING)
	for component in snapshot["operation_components"]:
		component["operation_product_in_components"] = []

	report = validators.evaluate_recipe(snapshot)
	assert report.verdict.allowed is False
	assert report.verdict.errors == (validators.NO_INPUT_COMPONENTS,)
	assert report.failed_validators() == ("operation_input_components",)

	snapshot["operation_components"] = []
	empty = validators.evaluate_recipe(snapshot)
	assert empty.verdict.errors == (validators.EMPTY_TECHNOLOGY_TREE,)


def test_tc_w1_016_output_unit_mismatch_fails_the_unit_validator(site):
	"""TC-W1-016 step 1 (URS-W1-015 AC-1): a production unit differing from the output
	item's stock UoM fails `checkIfUnitsInTechnologyMatch`
	(`TechnologyValidationService.java:641-676`) and adds the aggregate tree error."""
	snapshot = governance.recipe_snapshot(BOM_NAME, ROUTING)
	snapshot["operation_components"][0]["production_in_one_cycle_unit"] = "Nos"

	report = validators.evaluate_recipe(snapshot)
	assert report.verdict.errors == (
		validators.OUTPUT_UNITS_NOT_MATCH,
		validators.OPERATION_TREE_NOT_VALID,
	)
	assert report.findings[0].subject == "MIX/1"


def test_tc_w1_016_accepted_recipe_snapshot_passes_the_whole_battery(site):
	"""TC-W1-016 step 3 (URS-W1-015 AC-2): the corrected compound recipe passes every
	validator, so acceptance proceeds."""
	report = governance.evaluate_recipe(BOM_NAME, ROUTING)
	assert report.verdict.allowed is True
	assert report.failed_validators() == ()


# --------------------------------------------- TC-W1-030 / CHAR-TECH-VALIDATE-01, offline


def _characterisation_module(repo_root, name: str):
	"""Import `tests/characterisation/<name>.py` (read-only; the harness is W0-owned)."""
	tests_path = str(repo_root / "tests")
	if tests_path not in sys.path:
		sys.path.insert(0, tests_path)
	return importlib.import_module(f"characterisation.{name}")


def _parity_cases(repo_root):
	fixture = repo_root / "tests" / "characterisation" / "fixtures" / "technology_validation.json"
	return json.loads(fixture.read_text(encoding="utf-8"))["cases"]


def test_tc_w1_030_technology_validation_contract_resolves_to_production_code(repo_root):
	"""TC-W1-030 step 4 / `CHAR-TECH-VALIDATE-01` (URS-W1-015): the harness entrypoint
	`rheinwerk_mes.manufacturing_core.contracts.evaluate_technology` exists, so the parity
	contract no longer falls back to `tests/characterisation/legacy_rules.py`."""
	api = _characterisation_module(repo_root, "api")
	legacy = _characterisation_module(repo_root, "legacy_rules").evaluate_technology

	assert api.ENTRYPOINTS["technology_validation"] == (
		"rheinwerk_mes.manufacturing_core.contracts.evaluate_technology"
	)
	resolution = api.resolve("technology_validation", legacy)
	assert resolution.is_target_implementation is True
	assert resolution.callable_ is contracts.evaluate_technology


def test_tc_w1_030_technology_validation_parity_across_all_fixture_cases(repo_root):
	"""TC-W1-030 step 4 / `CHAR-TECH-VALIDATE-01` (URS-W1-015): every legacy case yields the
	same verdict and the same ordered message keys as Qcadoo
	(`TechnologyValidationService.java:91-707`)."""
	for case in _parity_cases(repo_root):
		verdict = contracts.evaluate_technology(case["technology"])
		assert verdict.allowed is bool(case["expected"]["allowed"]), case["id"]
		assert tuple(verdict.errors) == tuple(case["expected"]["errors"]), case["id"]


def test_tc_w1_030_verdict_shape_matches_the_harness_contract(repo_root):
	"""TC-W1-030 step 4 (URS-W1-015): the adapter returns the harness `Verdict` shape —
	`allowed` plus the ordered `errors` tuple."""
	verdict = contracts.evaluate_technology({"number": "BOM-X", "operation_components": []})
	assert verdict.allowed is False
	assert verdict.errors == (validators.EMPTY_TECHNOLOGY_TREE,)
	assert isinstance(verdict.errors, tuple)
