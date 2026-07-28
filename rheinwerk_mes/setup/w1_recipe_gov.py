"""W1-4 recipe-governance setup — one idempotent entry point (URS-W1-014 … URS-W1-017).

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the `patches.txt`
entry (existing sites), so a clean install and a migration converge on the same schema.
Everything the governance workflow needs is created here by committed code:

* the `rw_gov_state` Custom Field on the anchor `BOM` — the pill the technologist reads on
  the recipe itself (the anchor is never forked, ADR-006);
* the Frappe `Workflow` "Rheinwerk Rezeptfreigabe" carrying the `gov_state` transition set
  with its per-transition roles (URS-W1-014, URS-W1-029);
* the technologist's rights on the `Recipe Governance` DocType.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from rheinwerk_mes.recipe_isa88.governance import (
	ACCEPTED,
	CHECKED,
	DECLINED,
	DRAFT,
	GOVERNANCE_DOCTYPE,
	OUTDATED,
	TRANSITION_ROLES,
	TRANSITIONS,
)
from rheinwerk_mes.setup.roles import PLANNER, TECHNOLOGIST, WAREHOUSE_CLERK

ANCHOR_FIELD_MODULE = "Manufacturing Core"
WORKFLOW_NAME = "Rheinwerk Rezeptfreigabe"
GOV_STATE_FIELD = "rw_gov_state"

#: Pill styles per state (design skill § "Design tokens — Color": amber = hold,
#: green = released, red = stop, blue = informational). Frappe renders the workflow state
#: as a pill with icon + label + colour, so status is never colour-only.
STATE_STYLES: dict[str, str] = {
	DRAFT: "",
	CHECKED: "Warning",
	ACCEPTED: "Success",
	OUTDATED: "Inverse",
	DECLINED: "Danger",
}


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The single anchor-side field of W1-4: the recipe's governance state on the BOM."""
	return {
		"BOM": [
			{
				"fieldname": GOV_STATE_FIELD,
				"label": _("Freigabestatus"),
				"fieldtype": "Select",
				"options": "\n" + "\n".join(TRANSITIONS),
				"insert_after": "item_name",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"no_copy": 1,
				"description": _("Gepflegt über den Freigabedatensatz (Recipe Governance)."),
				# Anchor-side Custom Fields are grouped under Manufacturing Core (the W0
				# convention asserted by TC-W0-007); the governance DocTypes themselves live in
				# the Recipe ISA88 module.
				"module": ANCHOR_FIELD_MODULE,
			}
		]
	}


def install_custom_fields() -> list[str]:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	return [GOV_STATE_FIELD]


def workflow_definition() -> dict:
	"""The `gov_state` workflow: `TechnologyState.java:33-66` expressed in Frappe RBAC."""
	states = [
		{
			"state": state,
			"doc_status": "0",
			"allow_edit": TECHNOLOGIST if state in (DRAFT, CHECKED) else "System Manager",
			"style": STATE_STYLES[state],
		}
		for state in TRANSITIONS
	]
	transitions = [
		{
			"state": current,
			"action": _action_label(target),
			"next_state": target,
			"allowed": role,
			"allow_self_approval": 1,
		}
		for current, targets in TRANSITIONS.items()
		for target in targets
		for role in TRANSITION_ROLES
	]
	return {
		"doctype": "Workflow",
		"workflow_name": WORKFLOW_NAME,
		"document_type": GOVERNANCE_DOCTYPE,
		"workflow_state_field": "gov_state",
		"is_active": 1,
		"send_email_alert": 0,
		"states": states,
		"transitions": transitions,
	}


def _action_label(target: str) -> str:
	"""Action wording per target state — the glossary vocabulary, never invented."""
	return {
		DRAFT: "Zurück in Entwurf",
		CHECKED: "Prüfen",
		ACCEPTED: "Freigeben",
		OUTDATED: "Außer Kraft setzen",
		DECLINED: "Ablehnen",
	}[target]


def install_workflow() -> str:
	"""Create or refresh the workflow; safe to re-run."""
	definition = workflow_definition()
	for state in definition["states"]:
		if not frappe.db.exists("Workflow State", state["state"]):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state["state"]}).insert(
				ignore_permissions=True
			)
	for transition in definition["transitions"]:
		if not frappe.db.exists("Workflow Action Master", transition["action"]):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": transition["action"]}
			).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		doc = frappe.get_doc("Workflow", WORKFLOW_NAME)
		doc.update(
			{key: value for key, value in definition.items() if key not in ("doctype", "workflow_name")}
		)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(definition).insert(ignore_permissions=True)
	frappe.clear_cache(doctype=GOVERNANCE_DOCTYPE)
	return WORKFLOW_NAME


#: Governance rights: the technologist maintains recipes, planner and clerk read them.
PERMISSION_MATRIX = (
	(TECHNOLOGIST, {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1}),
	(PLANNER, {"read": 1, "report": 1, "export": 1, "print": 1}),
	(WAREHOUSE_CLERK, {"read": 1, "report": 1, "export": 1, "print": 1}),
)
_ALL_PTYPES = ("read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "print")


def install_permissions() -> None:
	"""Apply the governance RBAC baseline as Custom DocPerm rows; safe to re-run."""
	for role, permissions in PERMISSION_MATRIX:
		if not frappe.db.exists("Role", role):
			continue
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": GOVERNANCE_DOCTYPE, "role": role, "permlevel": 0}
		):
			add_permission(GOVERNANCE_DOCTYPE, role, 0)
		for ptype in _ALL_PTYPES:
			update_permission_property(
				GOVERNANCE_DOCTYPE, role, 0, ptype, permissions.get(ptype, 0), validate=False
			)
	frappe.clear_cache()


def setup_w1_recipe_gov() -> dict[str, object]:
	"""Create the W1-4 anchor field, `gov_state` workflow and governance RBAC."""
	summary = {
		"custom_fields": install_custom_fields(),
		"workflow": install_workflow(),
	}
	install_permissions()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_recipe_gov()
