"""Custom Field definitions extending the ERPNext `Workstation` anchor (URS-W0-005).

The `Workstation` anchor is never forked: the canonical Work Centre extension
(`production_line`, `division` — CDM-08, ADR-010) and the `legacy_refs` source-identifier
block land as Custom Fields owned by the `Manufacturing Core` module, so
`bench export-fixtures` and the app's `fixtures` hook carry them and the substrate stays
byte-identical to upstream. Labels are German-first (URS-W0-016) and passed through
`frappe._()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MANUFACTURING_CORE = "Manufacturing Core"

LEGACY_REFS_FIELDNAME = "legacy_refs"


def _legacy_refs_fields(insert_after: str, module: str) -> list[dict]:
	"""The `legacy_refs` source-identifier mapping block (URS-W0-003, URS-W0-014)."""
	return [
		{
			"fieldname": "rw_legacy_refs_section",
			"label": _("Herkunftssysteme"),
			"fieldtype": "Section Break",
			"insert_after": insert_after,
			"collapsible": 1,
			"module": module,
		},
		{
			"fieldname": LEGACY_REFS_FIELDNAME,
			"label": _("Legacy-Referenzen"),
			"fieldtype": "Table",
			"options": "Legacy Ref",
			"insert_after": "rw_legacy_refs_section",
			"module": module,
		},
	]


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The canonical Work Centre Custom Fields on the `Workstation` anchor (CDM-08)."""
	return {
		"Workstation": [
			{
				"fieldname": "rw_work_centre_section",
				"label": _("Betriebliche Zuordnung"),
				"fieldtype": "Section Break",
				"insert_after": "workstation_type",
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "production_line",
				"label": _("Fertigungslinie"),
				"fieldtype": "Link",
				"options": "Production Line",
				"insert_after": "rw_work_centre_section",
				"in_standard_filter": 1,
				"in_list_view": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "division",
				"label": _("Werksbereich"),
				"fieldtype": "Link",
				"options": "Division",
				"insert_after": "production_line",
				"in_standard_filter": 1,
				"module": MANUFACTURING_CORE,
			},
			*_legacy_refs_fields("disabled", MANUFACTURING_CORE),
		],
	}


def install_custom_fields() -> None:
	"""Create/refresh every Work Centre Custom Field; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()
