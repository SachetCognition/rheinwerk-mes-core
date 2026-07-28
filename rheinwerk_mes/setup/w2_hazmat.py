"""W2-7 installer — hazmat master data on the anchors (URS-W2-023, URS-W2-024).

The `Hazmat Profile` record and its children are app-owned DocTypes, so the only site
artefacts this installer creates are the Custom Fields that hang the profile off the anchor
`Item` and anchor `Batch` — the anchors themselves are never forked (programme rule 1):

| Anchor | Field | Purpose |
|---|---|---|
| `Item` | `rw_hazmat_profile` | the item's hazmat master data (URS-W2-023 AC-1) |
| `Item` | `rw_hazmat_mandatory` | hazmat-mandatory flag gating batch creation (AC-2) |
| `Batch` | `rw_hazmat_profile` | batch-level override for repacked goods (AC-1) |
| `Batch` | `rw_hazmat_un_number` / `rw_hazmat_storage_class` | read-only mirrors that make hazmat a *column* in any batch-backed stock view (URS-W2-024) |

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the `patches.txt`
entry (existing sites). Idempotent — safe to re-run. Design: `docs/design/W2-hazmat.md`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.regulatory_hazmat import profiles
from rheinwerk_mes.regulatory_hazmat.contracts import STORAGE_CLASSES

REGULATORY_HAZMAT = "Regulatory Hazmat"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The W2-7 Custom Fields on the anchor Item and anchor Batch."""
	return {
		"Item": [
			{
				"fieldname": "rw_hazmat_section",
				"label": _("Gefahrstoffdaten"),
				"fieldtype": "Section Break",
				"insert_after": "has_expiry_date",
				"collapsible": 0,
				"module": REGULATORY_HAZMAT,
			},
			{
				"fieldname": profiles.ITEM_PROFILE_FIELD,
				"label": _("Gefahrstoffprofil"),
				"fieldtype": "Link",
				"options": profiles.PROFILE_DOCTYPE,
				"insert_after": "rw_hazmat_section",
				"in_standard_filter": 1,
				"module": REGULATORY_HAZMAT,
			},
			{
				"fieldname": profiles.ITEM_MANDATORY_FIELD,
				"label": _("Gefahrstoffprofil vorgeschrieben"),
				"fieldtype": "Check",
				"default": "0",
				"description": _(
					"Chargen dieses Artikels können ohne verknüpftes Gefahrstoffprofil nicht "
					"angelegt werden (URS-W2-023)."
				),
				"insert_after": profiles.ITEM_PROFILE_FIELD,
				"module": REGULATORY_HAZMAT,
			},
		],
		"Batch": [
			{
				"fieldname": "rw_hazmat_section",
				"label": _("Gefahrstoffdaten"),
				"fieldtype": "Section Break",
				# After the W2-1/2/3 canonical-batch block, before the legacy-refs section.
				"insert_after": "qa_state_history",
				"module": REGULATORY_HAZMAT,
			},
			{
				"fieldname": profiles.BATCH_PROFILE_FIELD,
				"label": _("Gefahrstoffprofil (Charge)"),
				"fieldtype": "Link",
				"options": profiles.PROFILE_DOCTYPE,
				"description": _(
					"Nur für umgepackte oder umgefüllte Ware ausfüllen; leer = Profil des Artikels."
				),
				"insert_after": "rw_hazmat_section",
				"module": REGULATORY_HAZMAT,
			},
			{
				"fieldname": profiles.BATCH_UN_NUMBER_FIELD,
				"label": _("UN-Nummer"),
				"fieldtype": "Data",
				"read_only": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"insert_after": profiles.BATCH_PROFILE_FIELD,
				"module": REGULATORY_HAZMAT,
			},
			{
				"fieldname": profiles.BATCH_STORAGE_CLASS_FIELD,
				"label": _("Lagerklasse (TRGS 510)"),
				"fieldtype": "Data",
				"read_only": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"insert_after": profiles.BATCH_UN_NUMBER_FIELD,
				"module": REGULATORY_HAZMAT,
			},
		],
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def backfill_batch_mirrors() -> int:
	"""Refresh the read-only UN-number/Lagerklasse mirrors on existing batches.

	The mirrors are derived data (URS-W2-024); the profile links stay authoritative, so a
	re-run simply recomputes them without touching `modified`.
	"""
	updated = 0
	for batch in frappe.get_all("Batch", fields=["name", "item", profiles.BATCH_PROFILE_FIELD]):
		resolved = profiles.profile(
			batch.get(profiles.BATCH_PROFILE_FIELD) or profiles.item_profile_name(batch.item)
		)
		values = {
			profiles.BATCH_UN_NUMBER_FIELD: (resolved or {}).get("un_number"),
			profiles.BATCH_STORAGE_CLASS_FIELD: (resolved or {}).get("storage_class"),
		}
		current = frappe.db.get_value(
			"Batch",
			batch.name,
			[profiles.BATCH_UN_NUMBER_FIELD, profiles.BATCH_STORAGE_CLASS_FIELD],
			as_dict=True,
		)
		if current and all((current.get(key) or None) == (value or None) for key, value in values.items()):
			continue
		frappe.db.set_value("Batch", batch.name, values, update_modified=False)
		updated += 1
	return updated


def setup_w2_hazmat() -> dict[str, object]:
	"""Install every W2-7 site artefact; safe to re-run."""
	install_custom_fields()
	summary: dict[str, object] = {
		"custom_fields": sorted(
			field["fieldname"] for fields in custom_field_definitions().values() for field in fields
		),
		"storage_classes": len(STORAGE_CLASSES),
	}
	summary["batch_mirrors_refreshed"] = backfill_batch_mirrors()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_hazmat()
