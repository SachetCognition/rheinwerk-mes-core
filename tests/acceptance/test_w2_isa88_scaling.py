"""W2-6 — ISA-88 recipe scaling (URS-W2-021).

TC-W2-029: scaling a recipe to a target batch size is `Decimal`-exact and mass-balanced,
refuses to exceed a work centre's working-volume ceiling, never silently rounds a quantity
to zero, and yields a recipe that still passes the W1-4 validator battery.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
scaling = pytest.importorskip("rheinwerk_mes.recipe_isa88.scaling")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")

BOM_NAME = "BOM-RW-CHM-0003-001"


def _require_recipe(site) -> str:
	name = site.db.get_value("ISA88 Recipe", {"bom": BOM_NAME}, "name")
	if not name:
		pytest.skip("ISA-88 recipe fixture not seeded on this site")
	return name


def _charges(recipe) -> dict[str, float]:
	return {p.material: p.quantity for p in recipe.phases if p.material}


def test_scale_factor_is_decimal_exact():
	"""URS-W2-021 AC-1: the scale factor is exact `Decimal` division, offline."""
	assert scaling.scale_factor(500, 250) == Decimal("0.5")
	assert scaling.scale_factor(500, 375) == Decimal("0.75")
	assert scaling.scale_factor(400, 100) == Decimal("0.25")
	# A decimal factor 0.1 that binary float cannot represent exactly stays exact here.
	assert scaling.scale_factor(1000, 100) == Decimal("0.1")


def test_tc_w2_029_scaling_records_source_and_factor(site):
	"""TC-W2-029 step 1 (URS-W2-021 AC-1): scaling 500 kg → 250 kg halves every charge,
	records the source recipe and the scale factor 0.5, and starts a new governed Draft."""
	source = _require_recipe(site)
	scaled = scaling.scale_recipe(source, 250)

	assert scaled.source_recipe == source
	assert scaled.scale_factor == 0.5
	assert scaled.batch_size == 250.0
	assert _charges(scaled) == {"RW-CHM-0001": 240.0, "RW-CHM-0002": 10.0}
	assert governance.gov_state(scaled.bom) == governance.DRAFT


def test_tc_w2_029_mass_balance_preserved_for_non_integer_factor(site):
	"""TC-W2-029 step 2 (URS-W2-021 AC-1): a non-integer factor (0.75) keeps mass balance —
	the scaled charges sum to the scaled declared output, exactly under `Decimal`."""
	source = _require_recipe(site)
	scaled = scaling.scale_recipe(source, 375)

	charges = _charges(scaled)
	assert charges == {"RW-CHM-0001": 360.0, "RW-CHM-0002": 15.0}
	total = Decimal(str(charges["RW-CHM-0001"])) + Decimal(str(charges["RW-CHM-0002"]))
	assert total == Decimal(str(scaled.batch_size)) == Decimal("375")


def test_tc_w2_029_scaled_recipe_passes_the_w1_validator_battery(site):
	"""TC-W2-029 step 2 (URS-W2-021 / URS-W2-022): the scaled BOM version is a valid recipe —
	it passes the full W1-4 structural validator battery."""
	source = _require_recipe(site)
	scaled = scaling.scale_recipe(source, 250)

	report = governance.evaluate_recipe(scaled.bom)
	assert report.verdict.allowed, report.failed_validators()


def test_tc_w2_029_scaling_refused_above_work_centre_limit(site):
	"""TC-W2-029 step 3 (URS-W2-021 AC-2): MIX-01's 600 kg ceiling refuses a 750 kg scale,
	naming the unit procedure, the work centre and the limit."""
	source = _require_recipe(site)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		scaling.scale_recipe(source, 750)
	message = str(refusal.value)
	assert "MIX-01" in message
	assert "Mischen" in message
	assert "600" in message
	# Nothing was created — the check runs before any version is materialised.
	assert not site.db.exists("BOM", "BOM-RW-CHM-0003-002")


def test_tc_w2_029_sub_precision_quantity_is_flagged_not_zeroed(site):
	"""TC-W2-029 step 4 (URS-W2-021 AC-3): a scale that would round a charge below the kg
	precision is refused for technologist confirmation, naming the phase and material."""
	source = _require_recipe(site)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		scaling.scale_recipe(source, Decimal("0.1"))  # Additiv 20 kg → 0.004 kg
	message = str(refusal.value)
	assert "Dosieren Additiv" in message
	assert "RW-CHM-0002" in message


def test_tc_w2_029_confirmed_sub_precision_quantity_survives(site):
	"""TC-W2-029 step 4 (URS-W2-021 AC-3): once the technologist confirms, the sub-precision
	charge is preserved at full precision (never silently zeroed) and the recipe is flagged."""
	source = _require_recipe(site)
	scaled = scaling.scale_recipe(source, Decimal("0.1"), confirm_rounding=True)

	assert scaled.rounding_confirmation_required == 1
	additiv = next(p for p in scaled.phases if p.material == "RW-CHM-0002")
	assert additiv.quantity > 0
