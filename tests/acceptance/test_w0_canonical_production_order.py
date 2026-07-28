"""W0 canonical production order on the anchor `Work Order`.

TC-W0-008 (URS-W0-007) — CDM-02 extension fields present, `exec_state` workflow
deliberately absent (that is wave W1).
"""

from __future__ import annotations

ORDER = "PO-2026-0001"
EXTENSION_FIELDS = ("production_line", "master_order", "state_history")


def test_tc_w0_008_production_order_saved_with_extension_fields(site):
	"""TC-W0-008 step 1 (URS-W0-007 AC-1): PO-2026-0001 exists for 500 kg RW-CHM-0003 on
	LINE-1 against BOM-RW-CHM-0003-001, with the CDM-02 extension fields populated."""
	order = site.get_doc("Work Order", ORDER)
	assert order.production_item == "RW-CHM-0003"
	assert order.qty == 500.0
	assert order.stock_uom == "Kg"
	assert order.bom_no == "BOM-RW-CHM-0003-001"
	assert order.production_line == "LINE-1"
	assert order.meta.get_field("master_order").options == "Work Order"
	assert order.get("state_history") == []


def test_tc_w0_008_extension_fields_are_custom_not_anchor_schema(site):
	"""TC-W0-008 step 2 (URS-W0-007 AC-2): the extensions are `rheinwerk_mes` Custom
	Fields on an unforked anchor, readable through the document API."""
	anchor_module = site.db.get_value("DocType", "Work Order", "module")
	assert site.db.get_value("Module Def", anchor_module, "app_name") == "erpnext"
	for fieldname in EXTENSION_FIELDS:
		assert site.db.exists(
			"Custom Field",
			{"dt": "Work Order", "fieldname": fieldname, "module": "Manufacturing Core"},
		)
		assert not site.db.exists("DocField", {"parent": "Work Order", "fieldname": fieldname})


def test_tc_w0_008_state_history_container_carries_the_w1_state_machine(site):
	"""TC-W0-008 (URS-W0-007): the W0 `state_history` container needed no schema rework
	for W1 — the W1-1 `exec_state` machine (TC-W1-001) layers onto it as a Custom Field
	plus a workflow, with the anchor still unforked."""
	assert site.get_meta("Order State History").istable
	assert not site.db.exists("DocField", {"parent": "Work Order", "fieldname": "exec_state"})
	assert site.db.exists(
		"Custom Field", {"dt": "Work Order", "fieldname": "exec_state", "module": "Manufacturing Core"}
	)
