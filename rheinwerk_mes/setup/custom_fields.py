"""Custom Field definitions extending the ERPNext anchor DocTypes (W0).

The anchors (`Item`, `Workstation`, `BOM`, `Work Order`, `Warehouse`) are never
forked: every canonical-model extension below lands as a Custom Field owned by a
`rheinwerk_mes` module, so `bench --site … export-fixtures` and the app's
`fixtures` hook carry them and the substrate stays byte-identical to upstream.

Field-level mapping: `docs/canonical-model/README.md` — CDM-02 (production
order: `production_line`, `master_order`, `state_history`), CDM-08 (work centre:
`production_line`, `division`), CDM-03 (warehouse disposal strategy).
Labels are German-first (URS-W0-016) and passed through `frappe._()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MANUFACTURING_CORE = "Manufacturing Core"
WAREHOUSE = "Warehouse"

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
	"""All W0 Custom Fields, keyed by anchor DocType."""
	return {
		"Item": _legacy_refs_fields("barcodes", MANUFACTURING_CORE),
		"BOM": _legacy_refs_fields("backflush_based_on", MANUFACTURING_CORE),
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
		"Work Order": [
			{
				"fieldname": "production_line",
				"label": _("Fertigungslinie"),
				"fieldtype": "Link",
				"options": "Production Line",
				"insert_after": "company",
				"in_standard_filter": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "master_order",
				"label": _("Sammelauftrag"),
				"fieldtype": "Link",
				"options": "Work Order",
				"insert_after": "production_line",
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "rw_state_history_section",
				"label": _("Statusverlauf"),
				"fieldtype": "Section Break",
				"insert_after": "operations",
				"collapsible": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "state_history",
				"label": _("Statusverlauf"),
				"fieldtype": "Table",
				"options": "Order State History",
				"insert_after": "rw_state_history_section",
				"read_only": 1,
				"module": MANUFACTURING_CORE,
			},
			*_legacy_refs_fields("state_history", MANUFACTURING_CORE),
		],
		"Warehouse": [
			{
				"fieldname": "disposal_method",
				"label": _("Entnahmestrategie"),
				"fieldtype": "Select",
				"options": "\nFEFO\nFIFO\nLIFO",
				"insert_after": "warehouse_type",
				"in_standard_filter": 1,
				"module": WAREHOUSE,
			},
		],
	}


def install_custom_fields() -> None:
	"""Create/refresh every W0 Custom Field; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()
