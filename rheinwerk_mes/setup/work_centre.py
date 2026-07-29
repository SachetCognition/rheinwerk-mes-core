"""Canonical Work Centre setup — one idempotent entry point (URS-W0-005, CDM-08).

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and the `patches.txt`
entry (existing sites), so a clean install and a migration converge on the same schema.
Every artefact below is created by committed code; nothing is configured by hand.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.custom_fields import install_custom_fields


def setup_work_centre() -> None:
	"""Create/refresh the Work Centre Custom Fields on the `Workstation` anchor."""
	install_custom_fields()
	frappe.db.commit()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_work_centre()
