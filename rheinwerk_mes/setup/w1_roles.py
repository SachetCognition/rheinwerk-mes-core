"""W1-8 role model — workflow-state-level permissions (URS-W1-029, URS-W1-033).

Qcadoo gates state changes per *transition*, not per entity (dossier ch. 3.1 §B.2, 151
roles; §5.4 "who may change state"): a warehouse clerk may hold write rights on an order
and still be unable to accept it. Frappe expresses this in the `allowed` role of each
Workflow Transition row, which `rheinwerk_mes.manufacturing_core.exec_state` already
enforces — this module owns the matrix and levels the two programme workflows onto it:

* `Production Order Execution` (`exec_state`, W1-1)
* `Rheinwerk Rezeptfreigabe` (`gov_state`, W1-4) — applied only once that workflow exists, so
  this installer stays runnable while the parallel wave children land.

Per-DocType rights (W0, `rheinwerk_mes.setup.roles`) remain the floor; the transition
matrix is the ceiling. Every refusal is audited (URS-W1-029 AC-3, URS-W1-033).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.permissions import add_permission, update_permission_property
from frappe.utils import now_datetime

from rheinwerk_mes.manufacturing_core.exec_state import (
	ABANDONED,
	ACCEPTED,
	COMPLETED,
	DECLINED,
	IN_PROGRESS,
	INTERRUPTED,
	PENDING,
)
from rheinwerk_mes.manufacturing_core.exec_state import (
	WORKFLOW_NAME as EXEC_WORKFLOW,
)
from rheinwerk_mes.setup.roles import PLANNER, TECHNOLOGIST
from rheinwerk_mes.setup.w1_recipe_gov import WORKFLOW_NAME as RECIPE_GOV_WORKFLOW

OPERATOR = "Rheinwerk Shop Floor Operator"
BUSINESS_VIEWER = "Rheinwerk Business Viewer"

W1_ROLES = (OPERATOR, BUSINESS_VIEWER)

GOV_WORKFLOW = RECIPE_GOV_WORKFLOW

#: Append-only audit of refused transitions (`rheinwerk_mes` DocType, never an anchor).
REFUSAL_LOG = "Transition Refusal Log"

#: `exec_state`: (from, to, action) → the roles allowed to perform that transition.
EXEC_TRANSITION_ROLES: dict[tuple[str, str], tuple[str, ...]] = {
	(PENDING, ACCEPTED): (PLANNER,),
	(PENDING, IN_PROGRESS): (PLANNER,),
	(PENDING, DECLINED): (PLANNER,),
	(ACCEPTED, IN_PROGRESS): (PLANNER, OPERATOR),
	(ACCEPTED, DECLINED): (PLANNER,),
	(IN_PROGRESS, COMPLETED): (PLANNER, OPERATOR),
	(IN_PROGRESS, INTERRUPTED): (PLANNER, OPERATOR),
	(IN_PROGRESS, ABANDONED): (PLANNER,),
	(INTERRUPTED, IN_PROGRESS): (PLANNER, OPERATOR),
	(INTERRUPTED, ABANDONED): (PLANNER,),
}

#: `gov_state`: recipe governance belongs to the technologist; nobody else accepts a recipe.
GOV_TRANSITION_ROLES: dict[tuple[str, str], tuple[str, ...]] = {
	("Draft", "Checked"): (TECHNOLOGIST,),
	("Checked", "Accepted"): (TECHNOLOGIST,),
	("Checked", "Draft"): (TECHNOLOGIST,),
	("Accepted", "Outdated"): (TECHNOLOGIST,),
	("Draft", "Declined"): (TECHNOLOGIST,),
}

ACTION_LABELS: dict[tuple[str, str], str] = {
	(PENDING, ACCEPTED): "Accept",
	(PENDING, IN_PROGRESS): "Start",
	(PENDING, DECLINED): "Decline",
	(ACCEPTED, IN_PROGRESS): "Start",
	(ACCEPTED, DECLINED): "Decline",
	(IN_PROGRESS, COMPLETED): "Complete",
	(IN_PROGRESS, INTERRUPTED): "Interrupt",
	(IN_PROGRESS, ABANDONED): "Abandon",
	(INTERRUPTED, IN_PROGRESS): "Resume",
	(INTERRUPTED, ABANDONED): "Abandon",
}

READ_ONLY = {"read": 1, "report": 1, "export": 1}
EXECUTE = {"read": 1, "write": 1, "create": 1, "submit": 1, "print": 1, "report": 1}

#: (role, doctypes, permissions) — per-DocType floor for the two new W1 roles.
PERMISSION_MATRIX: tuple[tuple[str, tuple[str, ...], dict[str, int]], ...] = (
	(OPERATOR, ("Job Card",), EXECUTE),
	(OPERATOR, ("Work Order", "BOM", "Item", "Workstation", "Batch"), READ_ONLY),
	(BUSINESS_VIEWER, ("Work Order", "Job Card", "BOM", "Item"), READ_ONLY),
)

ALL_PERMISSION_TYPES = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"print",
)

#: Seeded personas that must hold the new roles (dossier personas, W0 fixtures).
PERSONA_ROLES: dict[str, tuple[str, ...]] = {
	"o.weber@rheinwerk-chemie.example": (OPERATOR,),
	"b.vogel@rheinwerk-chemie.example": (BUSINESS_VIEWER,),
}


def install_roles() -> list[str]:
	"""Create the two W1 roles; safe to re-run."""
	for role in W1_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1}).insert(
				ignore_permissions=True
			)
	return list(W1_ROLES)


def install_permissions() -> None:
	"""Apply the per-DocType floor as Custom DocPerm rows; safe to re-run."""
	for role, doctypes, permissions in PERMISSION_MATRIX:
		for doctype in doctypes:
			if not frappe.db.exists("DocType", doctype):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role, 0)
			for ptype in ALL_PERMISSION_TYPES:
				update_permission_property(doctype, role, 0, ptype, permissions.get(ptype, 0), validate=False)


def assign_persona_roles() -> dict[str, list[str]]:
	"""Give the seeded personas their W1 roles (no-op on a site without fixtures)."""
	assigned: dict[str, list[str]] = {}
	for email, roles in PERSONA_ROLES.items():
		if not frappe.db.exists("User", email):
			continue
		user = frappe.get_doc("User", email)
		held = {row.role for row in user.get("roles") or []}
		added = [role for role in roles if role not in held]
		for role in added:
			user.append("roles", {"role": role})
		if added:
			user.flags.ignore_permissions = True
			user.save()
		assigned[email] = added
	return assigned


def _apply_transition_roles(workflow_name: str, matrix: dict[tuple[str, str], tuple[str, ...]]) -> int:
	"""Rewrite a workflow's transition rows so each carries exactly its allowed roles."""
	if not frappe.db.exists("Workflow", workflow_name):
		return 0
	workflow = frappe.get_doc("Workflow", workflow_name)
	known_states = {row.state for row in workflow.states}
	existing_actions = {(row.state, row.next_state): row.action for row in workflow.transitions if row.action}
	rows = []
	for (from_state, to_state), roles in matrix.items():
		if from_state not in known_states or to_state not in known_states:
			continue
		action = existing_actions.get((from_state, to_state)) or ACTION_LABELS.get(
			(from_state, to_state), to_state
		)
		for role in roles:
			rows.append((from_state, to_state, action, role))
	if not rows:
		return 0
	workflow.set("transitions", [])
	for from_state, to_state, action, role in rows:
		_ensure_action(action)
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
	return len(rows)


def _ensure_action(action: str) -> None:
	if not frappe.db.exists("Workflow Action Master", action):
		frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
			ignore_permissions=True
		)


def allowed_roles(workflow_name: str, from_state: str, to_state: str) -> set[str]:
	"""Roles the installed workflow allows for one transition (empty = unrestricted)."""
	return set(
		frappe.get_all(
			"Workflow Transition",
			filters={"parent": workflow_name, "state": from_state, "next_state": to_state},
			pluck="allowed",
		)
	)


def may_transition(workflow_name: str, from_state: str, to_state: str, user: str | None = None) -> bool:
	"""True when `user` (default: the session user) may perform the transition."""
	roles = allowed_roles(workflow_name, from_state, to_state)
	if not roles:
		return True
	return bool(roles & set(frappe.get_roles(user or frappe.session.user)))


def log_transition_refusal(
	doctype: str, name: str, from_state: str, to_state: str, reason: str | None = None
) -> str:
	"""Audit a refused transition (URS-W1-029 AC-3, URS-W1-033): who, what, when.

	Written to the `Transition Refusal Log`, which no programme role may write or delete.
	"""
	roles = ", ".join(sorted(allowed_roles(EXEC_WORKFLOW, from_state, to_state)))
	entry = frappe.get_doc(
		{
			"doctype": REFUSAL_LOG,
			"reference_doctype": doctype,
			"reference_name": name,
			"from_state": from_state,
			"to_state": to_state,
			"refused_by": frappe.session.user,
			"refused_at": now_datetime(),
			"allowed_roles": roles,
			"message": reason
			or _("Der Übergang {0} → {1} ist der Rolle {2} vorbehalten.").format(
				_(from_state), _(to_state), roles or "—"
			),
		}
	)
	entry.flags.ignore_permissions = True
	entry.insert(ignore_permissions=True)
	return entry.name


def transition_refusals(doctype: str, name: str) -> list[dict[str, Any]]:
	"""Audited refusals for one record, newest first — the business viewer's audit view."""
	return frappe.get_all(
		REFUSAL_LOG,
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=["name", "from_state", "to_state", "refused_by", "refused_at", "message"],
		order_by="refused_at desc",
		ignore_permissions=True,
	)


def setup_w1_roles() -> dict[str, object]:
	"""Install every W1-8 site artefact; safe to re-run."""
	install_roles()
	install_permissions()
	summary: dict[str, object] = {
		"exec_transitions": _apply_transition_roles(EXEC_WORKFLOW, EXEC_TRANSITION_ROLES),
		"gov_transitions": _apply_transition_roles(GOV_WORKFLOW, GOV_TRANSITION_ROLES),
		"personas": assign_persona_roles(),
	}
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_roles()
