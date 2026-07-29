"""W1-1 installer — the `exec_state` Custom Field, workflow and transition roles (URS-W1-001).

Every site artefact the state machine needs is created here from committed code and
idempotently: the `exec_state` Custom Field on the anchor `Work Order`, the
`Production Order Execution` workflow whose transitions are exactly Qcadoo's
`canChangeTo` set, the planner role that owns approval (the shop floor acts through the
anchor's own `Manufacturing User`), and the two persona users.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the
`patches.txt` entry (existing sites). The anchor DocType is never forked.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

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
)

MANUFACTURING_CORE = "Manufacturing Core"

#: Role that may edit an order sitting in each state (Frappe's per-state `allow_edit`).
STATE_OWNERS: dict[str, str] = {
	PENDING: APPROVER_ROLE,
	ACCEPTED: OPERATOR_ROLE,
	IN_PROGRESS: OPERATOR_ROLE,
	INTERRUPTED: OPERATOR_ROLE,
	COMPLETED: APPROVER_ROLE,
	ABANDONED: APPROVER_ROLE,
	DECLINED: APPROVER_ROLE,
}

#: Anchor docstatus every state maps to. The order is executed as a submitted document,
#: and mapping all seven states to that one docstatus is what keeps `exec_state`
#: user-owned: submitting an order leaves its state untouched (Frappe only rewrites the
#: state when the docstatus it maps to changes) and a transition is a plain save that
#: never cancels or amends the anchor (ADR-004).
SUBMITTED = 1

#: Work Order rights of the approver role; the operator keeps the anchor's own rights.
APPROVER_ORDER_PERMISSIONS = {
	"read": 1,
	"write": 1,
	"create": 1,
	"submit": 1,
	"cancel": 1,
	"amend": 1,
	"report": 1,
	"export": 1,
	"print": 1,
}

#: Persona users of dossier ch. 3.2 that carry the transition roles (AC-2, AC-3).
PERSONAS = (
	{
		"email": "p.krueger@rheinwerk-chemie.example",
		"first_name": "Petra",
		"last_name": "Krüger",
		"role": APPROVER_ROLE,
	},
	{
		"email": "o.weber@rheinwerk-chemie.example",
		"first_name": "Oliver",
		"last_name": "Weber",
		"role": OPERATOR_ROLE,
	},
)


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The `exec_state` Custom Field on the anchor Work Order (CDM-02)."""
	return {
		"Work Order": [
			{
				"fieldname": "exec_state",
				"label": _("Ausführungszustand"),
				"fieldtype": "Select",
				"options": "\n".join(STATES),
				"default": INITIAL_STATE,
				"insert_after": "status",
				# Written by the workflow, never typed into: the transition actions own it.
				"read_only": 1,
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"in_list_view": 1,
				"module": MANUFACTURING_CORE,
			}
		]
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def install_roles() -> list[str]:
	"""Create the approver role with its Work Order rights; safe to re-run."""
	if not frappe.db.exists("Role", APPROVER_ROLE):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": APPROVER_ROLE,
				"desk_access": 1,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists(
		"Custom DocPerm",
		{"parent": "Work Order", "role": APPROVER_ROLE, "permlevel": 0},
	):
		add_permission("Work Order", APPROVER_ROLE, 0)
	for ptype, value in APPROVER_ORDER_PERMISSIONS.items():
		update_permission_property("Work Order", APPROVER_ROLE, 0, ptype, value, validate=False)
	return [APPROVER_ROLE]


def install_personas() -> list[str]:
	"""Create the planner and operator personas with their transition role; safe to re-run."""
	for persona in PERSONAS:
		if not frappe.db.exists("User", persona["email"]):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": persona["email"],
					"first_name": persona["first_name"],
					"last_name": persona["last_name"],
					"send_welcome_email": 0,
					"user_type": "System User",
					"language": "de",
				}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", persona["email"])
		if persona["role"] not in {row.role for row in user.roles}:
			user.add_roles(persona["role"])
	return [persona["email"] for persona in PERSONAS]


def _install_workflow_states() -> None:
	"""Workflow States carrying the status-pill style of each glossary state."""
	for state in STATES:
		if frappe.db.exists("Workflow State", state):
			frappe.db.set_value("Workflow State", state, "style", STATE_STYLES[state])
			continue
		frappe.get_doc(
			{
				"doctype": "Workflow State",
				"workflow_state_name": state,
				"style": STATE_STYLES[state],
			}
		).insert(ignore_permissions=True)


def _install_workflow_actions() -> None:
	for _from_state, _to_state, action, _role in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def install_workflow() -> str:
	"""Create or refresh the `exec_state` workflow on the anchor Work Order; safe to re-run."""
	_install_workflow_states()
	_install_workflow_actions()

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
			# `exec_state` is user-owned and orthogonal to the anchor's own
			# draft/submitted/cancelled docstatus, which stays untouched.
			"override_status": 0,
		}
	)
	workflow.set("states", [])
	for state in STATES:
		workflow.append(
			"states",
			{
				"state": state,
				"doc_status": SUBMITTED,
				"allow_edit": STATE_OWNERS[state],
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
	"""Give orders that predate the workflow the initial state, so it has a starting point."""
	names = frappe.get_all(
		"Work Order",
		filters={"exec_state": ("in", ("", None))},
		pluck="name",
		limit_page_length=0,
	)
	for name in names:
		frappe.db.set_value("Work Order", name, "exec_state", INITIAL_STATE, update_modified=False)
	return len(names)


def setup_w1_exec_state() -> dict[str, object]:
	"""Install every W1-1 site artefact; safe to re-run."""
	install_custom_fields()
	summary: dict[str, object] = {
		"roles": install_roles(),
		"personas": install_personas(),
		"workflow": install_workflow(),
	}
	summary["backfilled_orders"] = backfill_exec_state()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_exec_state()
