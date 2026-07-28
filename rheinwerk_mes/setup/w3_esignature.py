"""W3 installer — electronic-signature enforcement (DEC-W2-029 · URS-W2-029 AC-2).

The `Electronic Signature` DocType itself ships as app metadata; what needs installing is
the permission surface: signers create their own signatures through the whitelisted
`esignature.sign` (which inserts with `ignore_permissions`), so no role gets *write* access
to a signature — only read, so the signature report is visible to quality and to the
business viewer without anyone being able to edit the evidence.

Invoked from `after_install` and from `patches.txt`.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.compliance import esignature

SIGNATURE_DOCTYPE = esignature.DOCTYPE

#: role → permission types granted (nothing else is granted; write/create/delete never are).
READ_ONLY_ROLES: dict[str, tuple[str, ...]] = {
	"Quality Manager": ("read", "print", "export", "report"),
	"Rheinwerk Business Viewer": ("read", "print", "report"),
	"Rheinwerk Technologist": ("read", "print", "report"),
}

ALL_PERMISSION_TYPES: tuple[str, ...] = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"export",
	"report",
	"share",
)


def setup_w3_esignature() -> None:
	if not frappe.db.exists("DocType", SIGNATURE_DOCTYPE):
		return
	for role, granted in READ_ONLY_ROLES.items():
		if not frappe.db.exists("Role", role):
			continue
		_level_permissions(role, granted)
	frappe.clear_cache(doctype=SIGNATURE_DOCTYPE)


def _level_permissions(role: str, granted: tuple[str, ...]) -> None:
	"""Set exactly `granted` for `role`, zeroing every other permission type."""
	name = frappe.db.get_value("Custom DocPerm", {"parent": SIGNATURE_DOCTYPE, "role": role, "permlevel": 0})
	values = {permission: 1 if permission in granted else 0 for permission in ALL_PERMISSION_TYPES}
	if name:
		frappe.db.set_value("Custom DocPerm", name, values)
		return
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": SIGNATURE_DOCTYPE,
			"role": role,
			"permlevel": 0,
			**values,
		}
	).insert(ignore_permissions=True)


def execute() -> None:
	setup_w3_esignature()
