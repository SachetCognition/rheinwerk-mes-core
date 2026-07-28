"""W2 fan-in RBAC floor: the business viewer's read surface (URS-W2-036 AC-2).

The module children each granted their own role rows — the quality child for inspections and
certificates, the warehouse child for its journeys — but URS-W2-036 AC-2 is a *cross-module*
requirement: B. Vogel must be able to read **every** W2 screen while holding no
state-changing right anywhere. The read-only floor over the W2 surfaces the W1 matrix never
covered (the canonical Batch behind the Trace Ribbon, the genealogy links, the warehouse
journeys and their handling units) is therefore levelled here, at fan-in.

Read-only means read/report/export/print and nothing else: every permission type not named
is explicitly written as 0, so a role row another wave widens is levelled back rather than
silently left open (TC-W2-050 step 3 asserts exactly that).
"""

from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

from rheinwerk_mes.setup.w1_roles import (
	ALL_PERMISSION_TYPES,
	BUSINESS_VIEWER,
	READ_ONLY,
)

#: The W2 read surface: what the ribbon, the trace views and the warehouse journeys show.
VIEWER_READ_SURFACE: tuple[str, ...] = (
	"Batch",
	"Genealogy Link",
	"Tracking Record",
	"Stocktaking",
	"Repacking",
	"Handling Unit",
	"Storage Location",
	"CoA Certificate",
	"Quality Inspection",
)

#: Print is part of reading a certificate or a count sheet — the viewer takes paper to a
#: meeting; it changes nothing.
VIEWER_PERMISSIONS = {**READ_ONLY, "print": 1}


def install_viewer_read_surface() -> list[str]:
	"""Level the business viewer onto read-only across the W2 surfaces; safe to re-run."""
	applied: list[str] = []
	for doctype in VIEWER_READ_SURFACE:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": doctype, "role": BUSINESS_VIEWER, "permlevel": 0}
		):
			add_permission(doctype, BUSINESS_VIEWER, 0)
		for ptype in ALL_PERMISSION_TYPES:
			update_permission_property(
				doctype,
				BUSINESS_VIEWER,
				0,
				ptype,
				VIEWER_PERMISSIONS.get(ptype, 0),
				validate=False,
			)
		applied.append(doctype)
	return applied


def setup_w2_rbac() -> None:
	"""Installer entrypoint (`patches.txt`, `after_install`)."""
	install_viewer_read_surface()
	frappe.clear_cache()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_rbac()
