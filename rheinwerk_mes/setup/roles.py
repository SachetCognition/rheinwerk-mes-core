"""Access-control baseline for canonical master data (URS-W0-017).

W0 is *per-DocType* RBAC only — workflow-state-level permissions arrive with the W1
execution gating. The three programme roles are created from committed code and layered
onto the ERPNext anchors as Custom DocPerm rows through `frappe.permissions.add_permission`,
which first copies the substrate's standard permissions into Custom DocPerm so no upstream
ERPNext role loses access.

* technologist — creates and maintains canonical master data
* planner — read-only on master data, maintains production orders
* warehouse clerk — read-only on master data
"""

from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

TECHNOLOGIST = "Rheinwerk Technologist"
PLANNER = "Rheinwerk Planner"
WAREHOUSE_CLERK = "Rheinwerk Warehouse Clerk"

ROLES = (TECHNOLOGIST, PLANNER, WAREHOUSE_CLERK)

MASTER_DATA_DOCTYPES = (
	"Item",
	"Item Group",
	"UOM",
	"UOM Conversion Factor",
	"Workstation",
	"Workstation Type",
	"Operation",
	"Routing",
	"BOM",
	"Warehouse",
)

PRODUCTION_ORDER_DOCTYPES = ("Work Order", "Job Card")

READ_ONLY = {"read": 1, "report": 1, "export": 1}
MAINTAIN = {
	"read": 1,
	"write": 1,
	"create": 1,
	"delete": 1,
	"submit": 1,
	"cancel": 1,
	"amend": 1,
	"report": 1,
	"export": 1,
	"print": 1,
}

# (role, doctypes, permissions); every permission type in MAINTAIN is written for every
# rule, so a re-run narrows as well as widens and the matrix stays the single source.
PERMISSION_MATRIX = (
	(TECHNOLOGIST, MASTER_DATA_DOCTYPES, MAINTAIN),
	(TECHNOLOGIST, PRODUCTION_ORDER_DOCTYPES, READ_ONLY),
	(PLANNER, MASTER_DATA_DOCTYPES, READ_ONLY),
	(PLANNER, PRODUCTION_ORDER_DOCTYPES, MAINTAIN),
	(WAREHOUSE_CLERK, MASTER_DATA_DOCTYPES, READ_ONLY),
	(WAREHOUSE_CLERK, PRODUCTION_ORDER_DOCTYPES, READ_ONLY),
)


def install_roles() -> list[str]:
	"""Create the three programme roles; safe to re-run."""
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1}).insert(
				ignore_permissions=True
			)
	return list(ROLES)


def install_permissions() -> None:
	"""Apply the W0 RBAC baseline as Custom DocPerm rows; safe to re-run."""
	for role, doctypes, permissions in PERMISSION_MATRIX:
		for doctype in doctypes:
			if not frappe.db.exists("DocType", doctype):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role, 0)
			for ptype in MAINTAIN:
				update_permission_property(doctype, role, 0, ptype, permissions.get(ptype, 0), validate=False)
	frappe.clear_cache()
