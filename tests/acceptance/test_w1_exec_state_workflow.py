"""TC-W1-001 — `exec_state` workflow lifecycle on the anchor Work Order (URS-W1-001).

The offline tests assert the vocabulary and transition table (state names are law); the
site-backed tests drive the fixture order PO-2026-0001 through the acceptance criteria
as the personas that own the transitions.
"""

from __future__ import annotations

import pytest

from rheinwerk_mes.manufacturing_core.exec_state import (
	ABANDONED,
	ACCEPTED,
	APPROVER_ROLE,
	COMPLETED,
	DECLINED,
	IN_PROGRESS,
	INITIAL_STATE,
	INTERRUPTED,
	OPERATOR_ROLE,
	PENDING,
	STATE_STYLES,
	STATES,
	TRANSITIONS,
	WORKFLOW_NAME,
	allowed_targets,
	transition,
)
from rheinwerk_mes.setup.w1_exec_state import setup_w1_exec_state

PLANNER = "p.krueger@rheinwerk-chemie.example"
OPERATOR = "o.weber@rheinwerk-chemie.example"

#: Qcadoo `OrderState.canChangeTo` (`OrderState.java:31-81`), state for state.
QCADOO_CAN_CHANGE_TO = {
	PENDING: {ACCEPTED, IN_PROGRESS, DECLINED},
	ACCEPTED: {IN_PROGRESS, DECLINED},
	IN_PROGRESS: {COMPLETED, INTERRUPTED, ABANDONED},
	INTERRUPTED: {IN_PROGRESS, ABANDONED},
	COMPLETED: set(),
	DECLINED: set(),
	ABANDONED: set(),
}


def test_state_vocabulary_is_the_glossary_vocabulary():
	"""Design skill §"State names are law": the seven glossary terms, verbatim."""
	assert set(STATES) == {
		"Pending",
		"Accepted",
		"In Progress",
		"Completed",
		"Interrupted",
		"Abandoned",
		"Declined",
	}
	assert INITIAL_STATE == "Pending"


def test_transition_table_matches_the_qcadoo_transition_set():
	"""URS-W1-001: the workflow's transitions are the absorbed `canChangeTo` set."""
	assert {state: set(allowed_targets(state)) for state in STATES} == QCADOO_CAN_CHANGE_TO


def test_every_state_carries_a_status_pill_style():
	"""Design skill §"Component rules": `exec_state` renders as icon+label+colour."""
	assert set(STATE_STYLES) == set(STATES)
	assert all(STATE_STYLES[state] for state in STATES)


def test_interrupt_and_resume_are_role_gated_to_the_shop_floor():
	"""AC-3: the operator owns Interrupted and the resume back to In Progress."""
	roles = {(from_state, to_state): role for from_state, to_state, _action, role in TRANSITIONS}
	assert roles[(IN_PROGRESS, INTERRUPTED)] == OPERATOR_ROLE
	assert roles[(INTERRUPTED, IN_PROGRESS)] == OPERATOR_ROLE
	assert roles[(PENDING, ACCEPTED)] == APPROVER_ROLE


@pytest.fixture
def installed(site):
	"""The W1-1 site artefacts, installed idempotently for this test."""
	setup_w1_exec_state()
	return site


FINISHED_ITEM = "RW-CHM-0003"
RAW_ITEM = "RW-CHM-0002"


def _item(frappe, item_code: str, item_name: str) -> str:
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_name,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Kg" if frappe.db.exists("UOM", "Kg") else "Nos",
				"is_stock_item": 1,
				"valuation_rate": 10,
			}
		).insert()
	return item_code


@pytest.fixture
def recipe(installed) -> str:
	"""BOM-RW-CHM-0003-001 — the recipe PO-2026-0001 is produced against."""
	frappe = installed
	_item(frappe, RAW_ITEM, "Tensid-Vorstufe RW-CHM-0002")
	_item(frappe, FINISHED_ITEM, "Reinigungskonzentrat RW-CHM-0003")
	existing = frappe.db.get_value("BOM", {"item": FINISHED_ITEM, "docstatus": 1}, "name")
	if existing:
		return existing
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": FINISHED_ITEM,
			"quantity": 1,
			"company": _company(frappe),
			"items": [{"item_code": RAW_ITEM, "qty": 1}],
		}
	)
	bom.insert()
	bom.submit()
	return bom.name


def _company(frappe) -> str:
	return frappe.defaults.get_defaults().get("company") or frappe.db.get_value("Company", {}, "name")


@pytest.fixture
def production_order(installed, recipe):
	"""PO-2026-0001 — 500 kg RW-CHM-0003 against the Accepted recipe on LINE-1."""
	frappe = installed
	order = frappe.new_doc("Work Order")
	order.production_item = FINISHED_ITEM
	order.bom_no = recipe
	order.qty = 500
	order.company = _company(frappe)
	order.skip_transfer = 1
	order.wip_warehouse = order.fg_warehouse = order.source_warehouse = frappe.db.get_value(
		"Warehouse", {"company": order.company, "is_group": 0}, "name"
	)
	order.insert()
	return order


def test_ac_1_a_new_order_is_pending(production_order):
	"""AC-1: a newly created production order carries `exec_state` = Pending."""
	assert production_order.exec_state == PENDING


def test_exec_state_is_a_custom_field_on_an_unforked_anchor(installed):
	"""URS-W1-001: the state lives in a `rheinwerk_mes` Custom Field, not in the anchor
	DocType, and the workflow is layered on top of it."""
	frappe = installed
	assert frappe.db.exists(
		"Custom Field",
		{"dt": "Work Order", "fieldname": "exec_state", "module": "Manufacturing Core"},
	)
	assert not frappe.db.exists("DocField", {"parent": "Work Order", "fieldname": "exec_state"})
	assert frappe.db.get_value(
		"Module Def", frappe.db.get_value("DocType", "Work Order", "module"), "app_name"
	) == ("erpnext")
	workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
	assert (
		workflow.document_type,
		workflow.workflow_state_field,
		workflow.is_active,
	) == (
		"Work Order",
		"exec_state",
		1,
	)
	assert {(row.state, row.next_state, row.action, row.allowed) for row in workflow.transitions} == {
		(from_state, to_state, action, role) for from_state, to_state, action, role in TRANSITIONS
	}


def test_submitting_the_anchor_does_not_move_the_state(installed, production_order):
	"""URS-W1-001: state is user-owned — submitting the anchor is not a transition."""
	frappe = installed
	production_order.submit()

	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == PENDING


def test_ac_2_planner_accepts_a_pending_order(installed, production_order):
	"""AC-2: P. Krüger transitions the Pending order to Accepted."""
	frappe = installed
	production_order.submit()
	frappe.set_user(PLANNER)

	transition(production_order.name, "Accept")

	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == ACCEPTED


def test_ac_3_operator_interrupts_and_resumes(installed, production_order):
	"""AC-3: O. Weber interrupts an In Progress order and resumes it back to In Progress."""
	frappe = installed
	production_order.submit()
	frappe.set_user(PLANNER)
	transition(production_order.name, "Accept")

	frappe.set_user(OPERATOR)
	transition(production_order.name, "Start")
	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == IN_PROGRESS

	transition(production_order.name, "Interrupt")
	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == INTERRUPTED

	transition(production_order.name, "Resume")
	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == IN_PROGRESS


def test_the_operator_may_not_accept_an_order(installed, production_order):
	"""URS-W1-001 role gating: acceptance is the planner's transition."""
	frappe = installed
	production_order.submit()
	frappe.set_user(OPERATOR)

	with pytest.raises((frappe.PermissionError, frappe.ValidationError)):
		transition(production_order.name, "Accept")

	assert frappe.db.get_value("Work Order", production_order.name, "exec_state") == PENDING
