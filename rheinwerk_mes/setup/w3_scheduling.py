"""W3-2 installer — schedule governance and work-centre capacity (URS-W3-005 … URS-W3-008).

Everything the finite-capacity layer needs on a site is created here, idempotently, from
committed code (programme rule 1):

* the *Line Schedule Governance* workflow carrying `schedule_state` with per-transition role
  gating — Draft → Approved / Rejected, planner only (URS-W3-005 AC-2, URS-W3-023 AC-1);
* the planner's read access to the anchor `Workstation.production_capacity` used by the slot
  search, and a default capacity of 1 where the anchor left it empty (URS-W3-008 AC-1);
* the schedule-board page permissions.

No anchor DocType is forked: the schedule DocTypes are new and owned by `rheinwerk_mes`, and
`production_capacity` is an existing anchor field that is only read.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from `patches.txt`
(existing sites), so both converge on the same schema.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.manufacturing_core.scheduling.schedule_state import (
	ACTIONS,
	APPROVED,
	DRAFT,
	REJECTED,
	STATES,
	WORKFLOW_NAME,
)
from rheinwerk_mes.setup.roles import PLANNER

SCHEDULE_DOCTYPE = "Line Schedule"
BOARD_PAGE = "schedule-board"

STATE_STYLES: dict[str, str] = {
	DRAFT: "Warning",
	APPROVED: "Success",
	REJECTED: "Danger",
}

#: (from, to, action, role) — the only two edges Qcadoo's `ScheduleState` DRAFT block allows.
TRANSITIONS: tuple[tuple[str, str, str, str], ...] = tuple(
	(from_state, to_state, ACTIONS[(from_state, to_state)], PLANNER)
	for from_state, to_state in ((DRAFT, APPROVED), (DRAFT, REJECTED))
)

#: Work centres whose slot search needs an explicit ceiling (URS-W3-008 AC-1).
DEFAULT_PRODUCTION_CAPACITY = 1


def _ensure_workflow_states() -> None:
	for state in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state,
					"style": STATE_STYLES[state],
				}
			).insert(ignore_permissions=True)


def _ensure_workflow_actions() -> None:
	for _from_state, _to_state, action, _role in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def install_workflow() -> str:
	"""Create/refresh the `schedule_state` workflow on `Line Schedule`; safe to re-run."""
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
			"document_type": SCHEDULE_DOCTYPE,
			"workflow_state_field": "schedule_state",
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": 0,
		}
	)
	workflow.set("states", [])
	for state in STATES:
		workflow.append("states", {"state": state, "doc_status": 0, "allow_edit": PLANNER})
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


def backfill_production_capacity() -> list[str]:
	"""Give every work centre an explicit `production_capacity` (anchor field, URS-W3-008)."""
	touched = []
	for name in frappe.get_all(
		"Workstation",
		filters={"production_capacity": ("in", (0, None))},
		pluck="name",
		limit_page_length=0,
	):
		frappe.db.set_value(
			"Workstation", name, "production_capacity", DEFAULT_PRODUCTION_CAPACITY, update_modified=False
		)
		touched.append(name)
	return touched


def install_page_permissions() -> None:
	"""The schedule board is a planner surface; viewers read it (design skill audiences)."""
	if not frappe.db.exists("Page", BOARD_PAGE):
		return
	page = frappe.get_doc("Page", BOARD_PAGE)
	held = {row.role for row in page.get("roles") or []}
	for role in (PLANNER, "Rheinwerk Business Viewer", "Manufacturing User", "System Manager"):
		if role not in held and frappe.db.exists("Role", role):
			page.append("roles", {"role": role})
	page.flags.ignore_permissions = True
	page.save(ignore_permissions=True)


def setup_w3_scheduling() -> dict[str, object]:
	"""Install every W3-2 site artefact; safe to re-run."""
	summary: dict[str, object] = {"workflow": install_workflow()}
	summary["capacity_backfilled"] = backfill_production_capacity()
	install_page_permissions()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w3_scheduling()
