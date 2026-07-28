"""W3-6 installer — ADR transport data at the shipping boundary (URS-W3-018).

W2-7 installed the hazmat master data (`rheinwerk_mes/setup/w2_hazmat.py`); W3-6 only
*extends* that profile, so this installer has very little site work to do:

1. reload the app-owned `Hazmat Profile` DocType, so an existing site gains the ADR fields
   (`adr_class`, `adr_class_designation`, `adr_packing_group`, `adr_tunnel_code`,
   `adr_label_numbers`, `adr_dispatch_ready`) without anyone touching a form by hand;
2. backfill the two derived, read-only fields — the German ADR class designation and the
   dispatch-readiness flag — on every existing profile, so the technologist sees which
   profiles the dispatch gate would refuse *before* a lorry is at the gate.

No anchor DocType is forked and no anchor Custom Field is needed: the ADR data lives on the
app-owned profile the anchors already link to (programme rule 1). The dispatch gate itself is
a `doc_events` hook in `hooks.py` (`regulatory_hazmat.dispatch`), the same registration the
W1 expiry hard stop uses.

Invoked from `after_install` (fresh site) and from the `patches.txt` entry (existing sites).
Idempotent — safe to re-run. Design: `docs/design/W3-hazmat-dispatch.md`.
"""

from __future__ import annotations

import frappe
from frappe import _

from rheinwerk_mes.regulatory_hazmat import contracts, profiles

REGULATORY_HAZMAT = "Regulatory Hazmat"

#: The ADR fields W3-6 adds to the app-owned profile (URS-W3-018).
ADR_FIELDS: tuple[str, ...] = (
	"adr_class",
	"adr_class_designation",
	"adr_packing_group",
	"adr_tunnel_code",
	"adr_label_numbers",
	"adr_dispatch_ready",
)


def reload_profile_doctype() -> None:
	"""Pull the extended `Hazmat Profile` schema onto an existing site."""
	frappe.reload_doc("regulatory_hazmat", "doctype", "hazmat_profile")


def backfill_adr_derived() -> int:
	"""Recompute the derived ADR fields on every profile; returns the number changed.

	Both are mirrors of maintained data (`contracts.ADR_CLASSES`, `contracts.adr_is_complete`),
	so a re-run simply recomputes them without touching `modified`.
	"""
	updated = 0
	for row in frappe.get_all(
		profiles.PROFILE_DOCTYPE,
		fields=["name", *contracts.ADR_REQUIRED_FIELDS, "adr_class_designation", "adr_dispatch_ready"],
	):
		designation = (
			_(contracts.ADR_CLASSES[row.adr_class]) if row.adr_class in contracts.ADR_CLASSES else None
		)
		ready = 1 if contracts.adr_is_complete(dict(row)) else 0
		if (row.adr_class_designation or None) == designation and int(row.adr_dispatch_ready or 0) == ready:
			continue
		frappe.db.set_value(
			profiles.PROFILE_DOCTYPE,
			row.name,
			{"adr_class_designation": designation, "adr_dispatch_ready": ready},
			update_modified=False,
		)
		updated += 1
	return updated


def setup_w3_hazmat() -> dict[str, object]:
	"""Install every W3-6 site artefact; safe to re-run."""
	reload_profile_doctype()
	summary: dict[str, object] = {
		"adr_fields": list(ADR_FIELDS),
		"adr_classes": len(contracts.ADR_CLASSES),
		"packing_groups": len(contracts.PACKING_GROUPS),
	}
	summary["profiles_backfilled"] = backfill_adr_derived()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w3_hazmat()
