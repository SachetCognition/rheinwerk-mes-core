"""Parity contract entrypoints for the manufacturing core (W0 handover → W1).

`tests/characterisation/api.ENTRYPOINTS` resolves the technology-validation contract
`CHAR-TECH-VALIDATE-01` to `rheinwerk_mes.manufacturing_core.contracts.evaluate_technology`.
This module is a thin adapter only: the behaviour lives with the recipe-governance
validators (`rheinwerk_mes/recipe_isa88/validators.py`, URS-W1-015), which re-implement
Qcadoo `TechnologyValidationService.java:91-707` over plain mappings, so the contract runs
offline and against production code.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rheinwerk_mes.recipe_isa88.validators import Verdict
from rheinwerk_mes.recipe_isa88.validators import evaluate_technology as _evaluate_technology


def evaluate_technology(technology: Mapping[str, Any]) -> Verdict:
	"""Structural verdict for one recipe snapshot (URS-W1-015, TC-W1-030 step 4)."""
	return _evaluate_technology(technology)
