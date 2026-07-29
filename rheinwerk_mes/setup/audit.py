"""Audit-trail site setup entry point (URS-W0-015).

Wired from `hooks.py` as both `after_install` and `after_migrate`, so a fresh
site and a migrated one converge on the same tracked doctypes.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.setup.property_setters import install_audit_trail


def setup_audit_trail() -> list[str]:
	"""Enable document versioning on the canonical master-data anchors."""
	enabled = install_audit_trail()
	frappe.db.commit()
	return enabled
