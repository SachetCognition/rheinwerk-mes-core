"""W2-8 warehouse-completion installer — idempotent, committed-code only (programme rule 1).

Creates everything the stocktaking, repacking and pallet-balance features need on a site:
the two journey Workflows (`Stocktaking Journey`, `Repacking Journey`) carrying the `state`
field with role gating to the warehouse clerk, mirroring the Qcadoo
`StocktakingState`/`RepackingState` transition sets (semantics only, never ported).

Split/repack lineage (CDM-01, distinct from production genealogy) reuses the anchor Batch's
own native `parent_batch` field — the substrate already models it (ERPNext batch splitting),
so no Custom Field and no fork are needed.

Invoked from `patches.txt` (fresh sites migrate straight after model sync, existing sites
on the next migrate), so both converge on the same schema.
"""

from __future__ import annotations

import frappe

WAREHOUSE_MODULE = "Warehouse"
WAREHOUSE_CLERK_ROLE = "Rheinwerk Warehouse Clerk"

#: (from, to, action, role) for each journey. Exact parity with the Qcadoo enums:
#: `StocktakingState.canChangeTo` (FINALIZED/FINISHED collapsed onto Accepted, URS-W2-026)
#: and `RepackingState.canChangeTo` (`SachetCognition/Chem_mes@master`).
STOCKTAKING_WORKFLOW = "Stocktaking Journey"
REPACKING_WORKFLOW = "Repacking Journey"

STOCKTAKING_TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
	("Draft", "In Progress", "Zählung starten", WAREHOUSE_CLERK_ROLE),
	("In Progress", "Accepted", "Inventur annehmen", WAREHOUSE_CLERK_ROLE),
	("Draft", "Rejected", "Inventur verwerfen", WAREHOUSE_CLERK_ROLE),
	("In Progress", "Rejected", "Inventur verwerfen", WAREHOUSE_CLERK_ROLE),
)

REPACKING_TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
	("Draft", "Accepted", "Umpacken annehmen", WAREHOUSE_CLERK_ROLE),
	("Draft", "Rejected", "Umpacken verwerfen", WAREHOUSE_CLERK_ROLE),
)

STATE_STYLES: dict[str, str] = {
	"Draft": "",
	"In Progress": "Primary",
	"Accepted": "Success",
	"Rejected": "Danger",
}


def _states_of(transitions: tuple[tuple[str, str, str, str], ...]) -> list[str]:
	ordered: list[str] = []
	for from_state, to_state, _action, _role in transitions:
		for state in (from_state, to_state):
			if state not in ordered:
				ordered.append(state)
	return ordered


def _ensure_workflow_states(states: list[str]) -> None:
	for state in states:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state,
					"style": STATE_STYLES.get(state, ""),
				}
			).insert(ignore_permissions=True)


def _ensure_workflow_actions(transitions: tuple[tuple[str, str, str, str], ...]) -> None:
	for _from_state, _to_state, action, _role in transitions:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def _install_workflow(name: str, doctype: str, transitions: tuple[tuple[str, str, str, str], ...]) -> str:
	"""Create/refresh a journey Workflow on `doctype.state`; safe to re-run."""
	states = _states_of(transitions)
	_ensure_workflow_states(states)
	_ensure_workflow_actions(transitions)

	workflow = (
		frappe.get_doc("Workflow", name) if frappe.db.exists("Workflow", name) else frappe.new_doc("Workflow")
	)
	workflow.update(
		{
			"workflow_name": name,
			"document_type": doctype,
			"workflow_state_field": "state",
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": 0,
		}
	)
	workflow.set("states", [])
	for state in states:
		workflow.append(
			"states",
			{"state": state, "doc_status": 0, "allow_edit": WAREHOUSE_CLERK_ROLE},
		)
	workflow.set("transitions", [])
	for from_state, to_state, action, role in transitions:
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
	workflow.save(ignore_permissions=True)
	return name


def setup_w2_warehouse() -> dict[str, object]:
	"""Create the W2-8 journey Workflows."""
	summary = {
		"stocktaking_workflow": _install_workflow(
			STOCKTAKING_WORKFLOW, "Stocktaking", STOCKTAKING_TRANSITIONS
		),
		"repacking_workflow": _install_workflow(REPACKING_WORKFLOW, "Repacking", REPACKING_TRANSITIONS),
	}
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_warehouse()
