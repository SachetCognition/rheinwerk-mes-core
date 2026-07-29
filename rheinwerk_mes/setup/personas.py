"""Programme persona users carrying the W0 role baseline (URS-W0-017).

The personas of dossier ch. 3.2 exist as real site users so the access-control
acceptance criteria are exercised through the same permission path as production
logins. Creation is idempotent and never widens an existing user's roles beyond the
persona's own role.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.roles import PLANNER, TECHNOLOGIST, WAREHOUSE_CLERK

PERSONAS = (
	{
		"email": "t.schmid@rheinwerk-chemie.example",
		"first_name": "Thomas",
		"last_name": "Schmid",
		"role": TECHNOLOGIST,
	},
	{
		"email": "p.krueger@rheinwerk-chemie.example",
		"first_name": "Petra",
		"last_name": "Krüger",
		"role": PLANNER,
	},
	{
		"email": "w.braun@rheinwerk-chemie.example",
		"first_name": "Wolfgang",
		"last_name": "Braun",
		"role": WAREHOUSE_CLERK,
	},
)


def install_personas() -> list[str]:
	"""Create the persona users and assign exactly their programme role; safe to re-run."""
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
