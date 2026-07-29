"""Custom Field definitions extending the ERPNext anchor DocTypes (W0).

The anchors are never forked: every canonical-model extension below lands as a
Custom Field owned by a `rheinwerk_mes` module, so `bench --site … export-fixtures`
and the app's `fixtures` hook carry them while the substrate stays byte-identical
to upstream.

Field-level mapping: `docs/canonical-model/README.md` — CDM-02 (production order:
`production_line`, `master_order`, `state_history`). The `exec_state` workflow is
deliberately absent; it lands in W1 on top of these containers (URS-W0-007).
Labels are German-first (URS-W0-016) and passed through `frappe._()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MANUFACTURING_CORE = "Manufacturing Core"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""All W0 Custom Fields, keyed by anchor DocType."""
	return {
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
		],
	}


def install_custom_fields() -> None:
	"""Create/refresh every W0 Custom Field; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()
