"""W3-5 installer — the SCADA/OPC-UA adapter's site artefacts (URS-W3-015 … URS-W3-017).

The DocTypes (`OPC UA Tag Mapping`, `OPC UA Tracking Event`) and the Desk pages ship with
the app, so this installer only creates what cannot be a file (programme rule 1 — nothing is
created by hand on a site):

* the **source-system account** `opcua@rheinwerk-chemie.example`: the adapter authenticates
  as this service account, which is what makes the gate-audit actor the *source system*
  rather than an operator (URS-W3-021, URS-W3-015 AC-1);
* the **adapter role** `Rheinwerk SCADA Adapter` with exactly the rights the ingestion needs
  (read the order, book the anchor Job Card, write tracking events);
* the technologist's / planner's rights on the two DocTypes (URS-W3-023: tag-mapping
  administration is the technologist's, unmatched-event disposition the planner's).

Invoked from `after_install` (fresh site) and from the `patches.txt` entry (existing sites).
Idempotent — safe to re-run. Design: `docs/design/W3-scada-opcua.md`.
"""

from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

from rheinwerk_mes.integration.scada.contracts import SOURCE_SYSTEM, SOURCE_SYSTEM_USER
from rheinwerk_mes.integration.scada.mapping import MAPPING_DOCTYPE
from rheinwerk_mes.setup.roles import PLANNER, TECHNOLOGIST

EVENT_DOCTYPE = "OPC UA Tracking Event"
ADAPTER_ROLE = "Rheinwerk SCADA Adapter"

#: (role, doctype, permission types) — the adapter may book what the equipment reports and
#: nothing else; the technologist owns the mappings; the planner clears the queue.
PERMISSION_MATRIX: tuple[tuple[str, str, tuple[str, ...]], ...] = (
	(ADAPTER_ROLE, EVENT_DOCTYPE, ("read", "write", "create", "report")),
	(ADAPTER_ROLE, MAPPING_DOCTYPE, ("read", "report")),
	(ADAPTER_ROLE, "Work Order", ("read", "report")),
	(ADAPTER_ROLE, "Job Card", ("read", "write", "report")),
	(TECHNOLOGIST, MAPPING_DOCTYPE, ("read", "write", "create", "delete", "report", "export")),
	(TECHNOLOGIST, EVENT_DOCTYPE, ("read", "report", "export")),
	(PLANNER, EVENT_DOCTYPE, ("read", "write", "report", "export")),
	(PLANNER, MAPPING_DOCTYPE, ("read", "report", "export")),
)


def install_role() -> str:
	if not frappe.db.exists("Role", ADAPTER_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": ADAPTER_ROLE, "desk_access": 1, "is_custom": 1}
		).insert(ignore_permissions=True)
	return ADAPTER_ROLE


def install_source_system_user() -> str:
	"""The service account the adapter acts as — the audit's actor (URS-W3-021)."""
	if not frappe.db.exists("User", SOURCE_SYSTEM_USER):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": SOURCE_SYSTEM_USER,
				"first_name": f"{SOURCE_SYSTEM} Adapter",
				"user_type": "System User",
				"send_welcome_email": 0,
				"language": "de",
			}
		)
		user.flags.ignore_permissions = True
		user.insert(ignore_permissions=True)
	user = frappe.get_doc("User", SOURCE_SYSTEM_USER)
	for role in (ADAPTER_ROLE, "Manufacturing User"):
		if frappe.db.exists("Role", role) and role not in {row.role for row in user.get("roles") or []}:
			user.append("roles", {"role": role})
	user.flags.ignore_permissions = True
	user.save(ignore_permissions=True)
	return SOURCE_SYSTEM_USER


def install_permissions() -> None:
	for role, doctype, ptypes in PERMISSION_MATRIX:
		if not (frappe.db.exists("Role", role) and frappe.db.exists("DocType", doctype)):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
			add_permission(doctype, role, 0)
		for ptype in ptypes:
			update_permission_property(doctype, role, 0, ptype, 1, validate=False)


def setup_w3_scada() -> dict[str, object]:
	"""Install every W3-5 site artefact; safe to re-run."""
	install_role()
	install_source_system_user()
	install_permissions()
	frappe.clear_cache()
	frappe.db.commit()
	return {
		"role": ADAPTER_ROLE,
		"source_system_user": SOURCE_SYSTEM_USER,
		"doctypes": [MAPPING_DOCTYPE, EVENT_DOCTYPE],
	}


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w3_scada()
