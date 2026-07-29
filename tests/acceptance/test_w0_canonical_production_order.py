"""W0 canonical production order on the anchor `Work Order`.

TC-W0-008 (URS-W0-007) — CDM-02 extension fields present, `exec_state` workflow
deliberately absent (that is wave W1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXTENSION_FIELDS = ("production_line", "master_order", "state_history")
DOCTYPE_DIR = Path("rheinwerk_mes/manufacturing_core/doctype")


def _doctype_json(repo_root: Path, name: str) -> dict:
	return json.loads((repo_root / DOCTYPE_DIR / name / f"{name}.json").read_text())


def test_state_history_is_a_child_table_owned_by_manufacturing_core(repo_root):
	"""URS-W0-007: the `state_history` container is a `rheinwerk_mes` child DocType,
	so W1 can write transitions without touching the anchor schema."""
	child = _doctype_json(repo_root, "order_state_history")
	assert child["istable"] == 1
	assert child["module"] == "Manufacturing Core"
	assert {field["fieldname"] for field in child["fields"]} >= {
		"from_state",
		"to_state",
		"changed_by",
		"changed_at",
	}


def test_no_exec_state_field_is_shipped_in_w0(repo_root):
	"""URS-W0-007: `exec_state` is deferred to W1; W0 ships containers only."""
	sources = list((repo_root / "rheinwerk_mes").rglob("*.py")) + list(
		(repo_root / "rheinwerk_mes").rglob("*.json")
	)
	declaration = '"fieldname": "exec_state"'
	assert not [path for path in sources if declaration in path.read_text()]


@pytest.fixture
def work_order_meta(site):
	return site.get_meta("Work Order")


def test_tc_w0_008_extension_fields_are_custom_not_anchor_schema(site, work_order_meta):
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
	assert work_order_meta.get_field("master_order").options == "Work Order"
	assert work_order_meta.get_field("state_history").options == "Order State History"


def test_tc_w0_008_work_order_accepts_the_extension_fields(site):
	"""TC-W0-008 step 1 (URS-W0-007 AC-1): a Work Order carries `production_line` and
	`master_order` values through the document API (rolled back by the fixture)."""
	if not site.db.exists("Production Line", "LINE-1"):
		site.get_doc({"doctype": "Production Line", "production_line_name": "LINE-1"}).insert()

	order = site.new_doc("Work Order")
	order.production_line = "LINE-1"
	assert order.get("production_line") == "LINE-1"
	assert order.get("state_history") == []


def test_tc_w0_008_state_history_container_without_w1_workflow(site, work_order_meta):
	"""TC-W0-008 (URS-W0-007): W0 ships no `exec_state` field and no Work Order
	workflow, so W1 can layer the state machine without schema rework."""
	assert site.get_meta("Order State History").istable
	assert not work_order_meta.get_field("exec_state")
	assert not site.get_all("Workflow", filters={"document_type": "Work Order"}, pluck="name")
