"""Custom Fields carrying the `exec_state` change audit on the anchor Work Order (URS-W1-003).

The anchor is never forked: `exec_state`, `exec_state_reason` and the
`state_history` child table land as Custom Fields owned by the Manufacturing Core
module, so `bench … export-fixtures` and the app's `fixtures` hook carry them while
the ERPNext substrate stays byte-identical to upstream.

Field-level mapping: `docs/canonical-model/README.md` — CDM-02 (`exec_state`,
`state_history`). Labels are German-first (URS-W0-016) via `frappe._()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.manufacturing_core.exec_state import INITIAL_STATE, STATES

MANUFACTURING_CORE = "Manufacturing Core"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The audit Custom Fields, keyed by anchor DocType."""
	return {
		"Work Order": [
			{
				"fieldname": "exec_state",
				"label": _("Ausführungszustand"),
				"fieldtype": "Select",
				"options": "\n".join(STATES),
				"default": INITIAL_STATE,
				"insert_after": "status",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "exec_state_reason",
				"label": _("Begründung der Zustandsänderung"),
				"fieldtype": "Small Text",
				"insert_after": "exec_state",
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "rw_state_history_section",
				"label": _("Zustandsverlauf"),
				"fieldtype": "Section Break",
				"insert_after": "operations",
				"collapsible": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "state_history",
				"label": _("Zustandsverlauf"),
				"fieldtype": "Table",
				"options": "Order State History",
				"insert_after": "rw_state_history_section",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": MANUFACTURING_CORE,
			},
		],
	}


def setup_state_audit() -> None:
	"""Create/refresh the audit Custom Fields; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()
	frappe.db.commit()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_state_audit()
