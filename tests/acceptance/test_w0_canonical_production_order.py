"""W0 canonical production order on the anchor `Work Order`.

TC-W0-008 (URS-W0-007) — CDM-02 extension fields present, `exec_state` workflow
deliberately absent (that is wave W1).
"""

from __future__ import annotations

ORDER = "PO-2026-0001"
EXTENSION_FIELDS = ("production_line", "master_order", "state_history")
# The offline CI job has no Frappe installed, so app modules are resolved through the
# connected site (`frappe.get_attr`) rather than imported at collection time.
SEED_PRODUCTION_ORDER = "rheinwerk_mes.fixtures.seed.seed_production_order"


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


def test_tc_w0_008_reseeding_does_not_duplicate_the_production_order(site):
	"""TC-W0-008 (URS-W0-007): re-seeding recognises the existing order by its fixture
	attributes, not by the generated name, which depends on year and series counter."""
	bom_no = site.db.get_value("Work Order", ORDER, "bom_no")
	before = site.get_all("Work Order", filters={"bom_no": bom_no}, pluck="name")
	assert site.get_attr(SEED_PRODUCTION_ORDER)(bom_no) == ORDER
	assert site.get_all("Work Order", filters={"bom_no": bom_no}, pluck="name") == before


def test_tc_w0_008_state_history_container_without_w1_workflow(site):
	"""TC-W0-008 (URS-W0-007): `state_history` is a container only — W0 ships no
	`exec_state` field and no Work Order workflow, so W1 can layer the state machine
	without schema rework."""
	assert site.get_meta("Order State History").istable
	assert not site.get_meta("Work Order").get_field("exec_state")
	assert not site.get_all("Workflow", filters={"document_type": "Work Order"}, pluck="name")
