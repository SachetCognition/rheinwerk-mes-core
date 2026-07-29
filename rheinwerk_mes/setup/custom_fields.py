"""Custom Fields this app owns on the anchor DocTypes (W1-1 · W1-4).

The anchors (`Work Order`, `BOM`) are never forked: the `exec_state` machine (CDM-02) and
the recipe `gov_state` (CDM-04) are added as Custom Fields so a clean install and a
migrated site converge. Created idempotently from `after_install` and re-applied from the
`patches.txt` entry so existing sites pick the fields up on `bench migrate`.
"""

from __future__ import annotations

from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.manufacturing_core.exec_state import INITIAL_STATE, STATES
from rheinwerk_mes.recipe_isa88.governance import STATES as GOV_STATES

MANUFACTURING_CORE = "Manufacturing Core"
RECIPE_ISA88 = "Recipe ISA88"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The W1 Custom Fields on the anchor Work Order (CDM-02) and BOM (CDM-04)."""
	return {
		"Work Order": [
			{
				"fieldname": "production_line",
				"label": _("Fertigungslinie"),
				"fieldtype": "Link",
				"options": "Production Line",
				"insert_after": "production_item",
				"in_standard_filter": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "exec_state",
				"label": _("Ausführungszustand"),
				"fieldtype": "Select",
				"options": "\n".join(STATES),
				"default": INITIAL_STATE,
				"insert_after": "production_line",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"in_list_view": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "exec_state_reason",
				"label": _("Begründung des Zustandswechsels"),
				"fieldtype": "Small Text",
				"insert_after": "exec_state",
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "shortfall_reason",
				"label": _("Begründung der Mindermenge"),
				"fieldtype": "Small Text",
				"insert_after": "exec_state_reason",
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "state_history",
				"label": _("Ausführungsverlauf"),
				"fieldtype": "Table",
				"options": "Order State History",
				"insert_after": "shortfall_reason",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
		],
		"BOM": [
			{
				"fieldname": "gov_state",
				"label": _("Freigabestatus"),
				"fieldtype": "Select",
				"options": "\n".join(("", *GOV_STATES)),
				"insert_after": "item",
				"in_standard_filter": 1,
				"allow_on_submit": 1,
				"module": RECIPE_ISA88,
			},
		],
	}


def install_custom_fields() -> None:
	"""Create/refresh the Custom Fields; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def execute() -> None:
	"""`patches.txt` entry — apply the fields on existing sites during `bench migrate`."""
	install_custom_fields()
