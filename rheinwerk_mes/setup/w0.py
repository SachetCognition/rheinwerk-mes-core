"""Wave W0 canonical-entity setup — one idempotent entry point.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the
`patches.txt` entry (existing sites), so a clean install and a migration converge
on the same schema. Every artefact below is created by committed code; nothing is
configured by hand on a site.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.custom_fields import install_custom_fields
from rheinwerk_mes.setup.locale import install_locale
from rheinwerk_mes.setup.naming import install_naming_series
from rheinwerk_mes.setup.property_setters import install_audit_trail, install_shelf_life_column
from rheinwerk_mes.setup.roles import install_permissions, install_roles


def setup_w0() -> dict[str, list[str]]:
	"""Create the W0 custom fields, locale, naming series, audit trail and RBAC baseline."""
	install_custom_fields()
	summary = {
		"locale": sorted(install_locale()),
		"shelf_life_column": install_shelf_life_column(),
		"naming_series": install_naming_series(),
		"audit_trail": install_audit_trail(),
		"roles": install_roles(),
	}
	install_permissions()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w0()
