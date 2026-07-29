"""Wave W0 site setup — one idempotent entry point.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the
`patches.txt` entry (existing sites), so a clean install and a migration converge on
the same configuration. Everything below is created by committed code; nothing is
configured by hand on a site.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.personas import install_personas
from rheinwerk_mes.setup.roles import install_permissions, install_roles


def setup_w0() -> dict[str, list[str]]:
	"""Create the W0 RBAC baseline and its persona users."""
	summary = {"roles": install_roles()}
	install_permissions()
	summary["personas"] = install_personas()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w0()
