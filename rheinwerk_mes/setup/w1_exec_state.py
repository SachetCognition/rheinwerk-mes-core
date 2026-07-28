"""W1-1 installer — `exec_state` custom fields, workflow and roles (URS-W1-001).

Everything the state machine needs on a site is created here from committed code and
idempotently: the `exec_state`/`exec_state_reason`/`shortfall_reason` Custom Fields on
the anchor `Work Order`, the `Production Order Execution` workflow whose transitions are
exactly Qcadoo's `canChangeTo` set (`OrderState.java:31-81`), and the role gating.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the
`patches.txt` entry (existing sites). The anchor DocType is never forked.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.manufacturing_core.exec_state import (
	ABANDONED,
	ACCEPTED,
	COMPLETED,
	DECLINED,
	IN_PROGRESS,
	INITIAL_STATE,
	INTERRUPTED,
	PENDING,
	STATES,
	WORKFLOW_NAME,
)
from rheinwerk_mes.setup.roles import PLANNER

MANUFACTURING_CORE = "Manufacturing Core"
OPERATOR_ROLE = "Manufacturing User"
APPROVER_ROLE = PLANNER

#: (from, to, action, role) — one row per Qcadoo legal transition (`OrderState.java:31-81`).
TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
	(PENDING, ACCEPTED, "Accept", APPROVER_ROLE),
	(PENDING, IN_PROGRESS, "Start", APPROVER_ROLE),
	(PENDING, DECLINED, "Decline", APPROVER_ROLE),
	(ACCEPTED, IN_PROGRESS, "Start", OPERATOR_ROLE),
	(ACCEPTED, DECLINED, "Decline", APPROVER_ROLE),
	(IN_PROGRESS, COMPLETED, "Complete", OPERATOR_ROLE),
	(IN_PROGRESS, INTERRUPTED, "Interrupt", OPERATOR_ROLE),
	(IN_PROGRESS, ABANDONED, "Abandon", APPROVER_ROLE),
	(INTERRUPTED, IN_PROGRESS, "Resume", OPERATOR_ROLE),
	(INTERRUPTED, ABANDONED, "Abandon", APPROVER_ROLE),
)

#: Desk pill styles per state (design skill § "Component rules").
STATE_STYLES: dict[str, str] = {
	PENDING: "Warning",
	ACCEPTED: "Info",
	IN_PROGRESS: "Primary",
	COMPLETED: "Success",
	INTERRUPTED: "Warning",
	ABANDONED: "Danger",
	DECLINED: "Danger",
}


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The W1-1 Custom Fields on the anchor Work Order (CDM-02)."""
	return {
		"Work Order": [
			{
				"fieldname": "exec_state",
				"label": _("Ausführungszustand"),
				"fieldtype": "Select",
				"options": "\n".join(STATES),
				"default": INITIAL_STATE,
				"insert_after": "production_line",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"in_list_view": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "exec_state_reason",
				"label": _("Begründung des Zustandswechsels"),
				"fieldtype": "Small Text",
				"insert_after": "exec_state",
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "shortfall_reason",
				"label": _("Begründung der Mindermenge"),
				"fieldtype": "Small Text",
				"insert_after": "exec_state_reason",
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
			# The W0 audit table must stay writable once the order is submitted.
			{
				"fieldname": "state_history",
				"label": _("Ausführungsverlauf"),
				"fieldtype": "Table",
				"options": "Order State History",
				"insert_after": "rw_state_history_section",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
		]
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def _ensure_workflow_states() -> None:
	for state in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": STATE_STYLES[state]}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Workflow State", state, "style", STATE_STYLES[state])


def _ensure_workflow_actions() -> None:
	for _from_state, _to_state, action, _role in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def install_workflow() -> str:
	"""Create/refresh the `exec_state` workflow on the anchor Work Order; safe to re-run."""
	_ensure_workflow_states()
	_ensure_workflow_actions()

	workflow = (
		frappe.get_doc("Workflow", WORKFLOW_NAME)
		if frappe.db.exists("Workflow", WORKFLOW_NAME)
		else frappe.new_doc("Workflow")
	)
	workflow.update(
		{
			"workflow_name": WORKFLOW_NAME,
			"document_type": "Work Order",
			"workflow_state_field": "exec_state",
			"is_active": 1,
			"send_email_alert": 0,
			# The anchor's own docstatus flow (draft/submit/cancel) stays untouched.
			"override_status": 0,
		}
	)
	workflow.set("states", [])
	roles_by_state = {PENDING: APPROVER_ROLE}
	for from_state, _to_state, _action, role in TRANSITIONS:
		roles_by_state.setdefault(from_state, role)
	for state in STATES:
		workflow.append(
			"states",
			{
				"state": state,
				"doc_status": 0,
				"allow_edit": roles_by_state.get(state, APPROVER_ROLE),
				"update_field": None,
			},
		)
	workflow.set("transitions", [])
	for from_state, to_state, action, role in TRANSITIONS:
		workflow.append(
			"transitions",
			{
				"state": from_state,
				"action": action,
				"next_state": to_state,
				"allowed": role,
				"allow_self_approval": 1,
			},
		)
	workflow.flags.ignore_permissions = True
	workflow.save()
	return workflow.name


def backfill_exec_state() -> int:
	"""Give existing orders the initial state so the workflow has a starting point."""
	rows = frappe.get_all(
		"Work Order", filters={"exec_state": ("in", ("", None))}, pluck="name", limit_page_length=0
	)
	for name in rows:
		frappe.db.set_value("Work Order", name, "exec_state", INITIAL_STATE, update_modified=False)
	return len(rows)


def setup_w1_exec_state() -> dict[str, object]:
	"""Install every W1-1 site artefact; safe to re-run."""
	install_custom_fields()
	summary: dict[str, object] = {"workflow": install_workflow()}
	summary["backfilled_orders"] = backfill_exec_state()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_exec_state()
