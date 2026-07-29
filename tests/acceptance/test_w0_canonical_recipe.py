"""W0 canonical BOM/Routing on unforked anchor DocTypes.

TC-W0-007 (URS-W0-006) — BOM-RW-CHM-0003-001 with routing RT-COMPOUND-01 and the
anchor's versioned naming.
"""

from __future__ import annotations

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"


def test_tc_w0_007_bom_and_routing_saved_on_anchors(site):
	"""TC-W0-007 step 1 (URS-W0-006 AC-1): the compound BOM is submitted on the anchor
	`BOM`, consumes both raw materials and runs the RT-COMPOUND-01 routing across the
	two LINE-1 work centres."""
	bom = site.get_doc("BOM", BOM_NAME)
	assert bom.docstatus == 1
	assert bom.item == "RW-CHM-0003"
	assert bom.uom == "Kg"
	assert bom.routing == ROUTING
	assert {row.item_code for row in bom.items} == {"RW-CHM-0001", "RW-CHM-0002"}
	assert [row.workstation for row in bom.operations] == ["MIX-01", "FILL-01"]

	routing = site.get_doc("Routing", ROUTING)
	assert [row.operation for row in routing.operations] == ["MIX", "FILL"]


def test_tc_w0_007_recipe_anchors_are_not_forked(site):
	"""TC-W0-007 (URS-W0-006): `BOM` and `Routing` remain substrate-owned; the app may
	only extend them through Custom Fields it owns."""
	for doctype in ("BOM", "Routing", "BOM Item", "BOM Operation"):
		module = site.db.get_value("DocType", doctype, "module")
		assert site.db.get_value("Module Def", module, "app_name") == "erpnext"

	app_modules = {
		row.name for row in site.get_all("Module Def", filters={"app_name": "rheinwerk_mes"}, fields=["name"])
	}
	for doctype in ("BOM", "Routing"):
		custom = site.get_all("Custom Field", filters={"dt": doctype}, fields=["fieldname", "module"])
		assert {row.module for row in custom} <= app_modules


def test_tc_w0_007_anchor_versioned_naming_distinguishes_versions(site):
	"""TC-W0-007 step 2 (URS-W0-006 AC-2): a second BOM for the same item is named
	`BOM-RW-CHM-0003-002` by the anchor's own versioned naming."""
	first = site.get_doc("BOM", BOM_NAME)
	second = site.copy_doc(first)
	second.is_default = 0
	second.is_active = 1
	second.insert()
	assert second.name == "BOM-RW-CHM-0003-002"
