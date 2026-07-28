"""W2-6 — ISA-88 recipe structure over the anchor BOM + Routing (URS-W2-020).

TC-W2-028: the recipe expresses the ISA-88 procedural hierarchy (unit procedures →
operations → phases) over the governed anchor BOM/Routing pair without forking either, and
a phase may only charge material the BOM knows.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
structure = pytest.importorskip("rheinwerk_mes.recipe_isa88.structure")

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"
RECIPE_DOCTYPES = ("ISA88 Recipe", "ISA88 Unit Procedure", "ISA88 Phase")


def _recipe(site):
	name = site.db.get_value("ISA88 Recipe", {"bom": BOM_NAME}, "name")
	if not name:
		pytest.skip("ISA-88 recipe fixture not seeded on this site")
	return site.get_doc("ISA88 Recipe", name)


def test_tc_w2_028_hierarchy_expressed_over_anchor_bom_and_routing(site):
	"""TC-W2-028 step 1 (URS-W2-020 AC-1): the seeded recipe carries the ISA-88 hierarchy —
	unit procedures bound to Routing operations + work centres, phases grouped onto them,
	each material phase drawn from the anchor BOM."""
	recipe = _recipe(site)
	assert recipe.bom == BOM_NAME
	assert recipe.routing == ROUTING
	assert recipe.batch_size == 500.0

	unit_procedures = {up.unit_procedure_id: up for up in recipe.unit_procedures}
	assert set(unit_procedures) == {"MISCHEN", "ABFUELLEN"}
	assert unit_procedures["MISCHEN"].workstation == "MIX-01"
	assert unit_procedures["MISCHEN"].operation == "MIX"
	assert unit_procedures["ABFUELLEN"].workstation == "FILL-01"

	# Every unit procedure binds an operation of the anchor Routing (never a fork of it).
	routing_ops = set(site.get_all("BOM Operation", filters={"parent": ROUTING}, pluck="operation"))
	for up in recipe.unit_procedures:
		assert site.db.exists("Operation", up.operation)
		assert up.operation in routing_ops

	charges = {p.material: p.quantity for p in recipe.phases if p.material}
	assert charges == {"RW-CHM-0001": 480.0, "RW-CHM-0002": 20.0}
	# The process phase carries a duration, not a material charge.
	mischen = next(p for p in recipe.phases if p.phase_name == "Mischen 30 min")
	assert not mischen.material and mischen.duration_min == 30.0


def test_tc_w2_028_anchor_doctypes_are_not_forked(site):
	"""TC-W2-028 step 2 (URS-W2-020 AC-2): the ISA-88 structure lives in app-owned DocTypes
	in the `Recipe ISA88` module; the anchor BOM/Routing keep their ERPNext schema — the
	ISA-88 fields are not grafted onto them."""
	for doctype in RECIPE_DOCTYPES:
		assert site.db.get_value("DocType", doctype, "module") == "Recipe ISA88"

	# BOM/Routing remain core ERPNext DocTypes, not re-homed into the app's module.
	assert site.db.get_value("DocType", "BOM", "module") == "Manufacturing"
	assert site.db.get_value("DocType", "Routing", "module") == "Manufacturing"

	# None of the ISA-88 procedural fields leaked onto the anchor BOM schema.
	bom_fields = {df.fieldname for df in site.get_meta("BOM").fields}
	assert not bom_fields & {"unit_procedures", "phases", "batch_size", "scale_factor"}


def test_tc_w2_028_phase_material_must_belong_to_the_bom(site):
	"""TC-W2-028 step 3 (URS-W2-020 AC-3): a phase charging material the BOM does not list is
	refused, naming both the phase and the material."""
	recipe = _recipe(site)
	recipe.append(
		"phases",
		{
			"unit_procedure": "MISCHEN",
			"phase_name": "Dosieren Fremdstoff",
			"phase_type": "Dosieren",
			"material": "RW-CHM-0003",  # the finished good, never a component of its own BOM
			"quantity": 5.0,
			"uom": "Kg",
		},
	)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		recipe.save()
	message = str(refusal.value)
	assert "Dosieren Fremdstoff" in message
	assert "RW-CHM-0003" in message


def test_tc_w2_028_phase_references_a_declared_unit_procedure(site):
	"""TC-W2-028 step 3 (URS-W2-020 AC-3): a phase whose grouping key names no unit
	procedure is refused, naming the phase."""
	recipe = _recipe(site)
	recipe.append(
		"phases",
		{"unit_procedure": "TROCKNEN", "phase_name": "Trocknen", "phase_type": "Verarbeiten"},
	)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		recipe.save()
	assert "Trocknen" in str(refusal.value)


def test_structure_helper_surface():
	"""The structure guard is a pure helper the controller and tests share (URS-W2-020)."""
	assert callable(structure.validate_structure)
	assert callable(structure.bom_component_items)
