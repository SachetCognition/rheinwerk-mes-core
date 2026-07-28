"""TC-W1-023 — legacy bridge affordance on renamed fields.

Verifies **URS-W1-022** (old Qcadoo/OFBiz names discoverable on hover, removable by feature
flag after cutover) through **TC-W1-023** of `docs/test/TST-W1-production-core.md`.
The hover itself is a Desk/terminal rendering of the field description asserted here at
its source: the hint the server publishes and the Property Setter it writes.
"""

from __future__ import annotations

import pytest

frappe = pytest.importorskip("frappe")
legacy_bridge = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.legacy_bridge")
w1_shopfloor = pytest.importorskip("rheinwerk_mes.setup.w1_shopfloor")


def test_recipe_field_offers_its_legacy_name(site):
	"""URS-W1-022 AC-1 / TC-W1-023 step 1 — the recipe field shows "was: Technology"."""
	w1_shopfloor.install_legacy_bridge(True)

	hint = legacy_bridge.legacy_hint("Work Order", "bom_no")

	assert hint == "früher: Technology"
	assert site.get_meta("Work Order").get_field("bom_no").description == hint


def test_hints_are_published_per_doctype(site):
	"""URS-W1-022 / TC-W1-023 — every renamed field of a screen is discoverable at once."""
	w1_shopfloor.install_legacy_bridge(True)
	hints = legacy_bridge.legacy_hints("Job Card")
	assert hints["operation"] == "früher: Technology operation component"
	assert hints["total_completed_qty"] == "früher: Done quantity"


def test_the_affordance_is_removable_by_feature_flag(site):
	"""URS-W1-022 AC-2 / TC-W1-023 step 2 — with the flag off no legacy name is shown."""
	legacy_bridge.set_enabled(False)
	try:
		assert legacy_bridge.is_enabled() is False
		assert legacy_bridge.legacy_hint("Work Order", "bom_no") is None
		assert legacy_bridge.legacy_hints("Work Order") == {}
		assert not site.get_meta("Work Order").get_field("bom_no").description
	finally:
		legacy_bridge.set_enabled(True)
