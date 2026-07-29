"""Wave W0 canonical-entity setup — one idempotent entry point.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the
`patches.txt` entry (existing sites), so a clean install and a migration converge
on the same schema. Every artefact below is created by committed code; nothing is
configured by hand on a site.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.custom_fields import install_custom_fields


def setup_w0() -> None:
	"""Create the W0 custom fields on the anchor DocTypes."""
	install_custom_fields()
	frappe.db.commit()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w0()
