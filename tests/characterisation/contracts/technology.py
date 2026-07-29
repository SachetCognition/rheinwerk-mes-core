"""Technology structural validator contract — CHAR-TECH-VALIDATE-01.

URS-W0-012 · TC-W0-014 (fixtures encoded in W0, consumed by W1).
Legacy baseline: `mes-plugins/mes-plugins-technologies/src/main/java/com/qcadoo/mes/
technologies/states/listener/TechnologyValidationService.java:91-707`
(`SachetCognition/Chem_mes@master`) — empty tree (:678-705), input-component quantities
(:91-144), unit matching (:546-676), technology in use by an active order (:232-238).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import evaluate_technology
from ..registry import Contract, register


def _check_technology(resolution: Resolution, case: Mapping[str, Any]) -> None:
	verdict = resolution.callable_(case["technology"])
	expected_allowed = bool(case["expected"]["allowed"])
	expected_errors = tuple(case["expected"]["errors"])
	assert verdict.allowed is expected_allowed, (
		f"{case['id']}: expected allowed={expected_allowed}, got {verdict.allowed} "
		f"(implementation: {resolution.source})"
	)
	assert tuple(verdict.errors) == expected_errors, (
		f"{case['id']}: expected errors {expected_errors}, got {tuple(verdict.errors)} "
		f"(implementation: {resolution.source})"
	)


TECHNOLOGY_VALIDATION = register(
	Contract(
		id="CHAR-TECH-VALIDATE-01",
		title="Technology structural validators: tree, input quantities, units, in-use refusals",
		concern="technology_validation",
		legacy_source="TechnologyValidationService.java:91-707",
		fixture="technology_validation.json",
		fallback=evaluate_technology,
		checker=_check_technology,
		urs_ids=("URS-W0-012",),
		tc_ids=("TC-W0-014",),
	)
)
