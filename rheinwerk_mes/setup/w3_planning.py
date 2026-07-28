"""Wave W3-1 planning setup — one idempotent entry point (Production Plan / MRP journey).

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from `patches.txt`
(existing sites), so a clean install and a migration converge on the same schema. Every
artefact is created by committed code — never by hand on a site (programme rule 1). No
anchor DocType is forked: the anchor `Production Plan` gains two Custom Fields owned by the
`rheinwerk_mes` app —

* `rw_production_line` — the target Fertigungslinie the generated Work Orders inherit
  (CDM-08); the anchor plan has no line concept.
* `rw_planner` — the responsible planner (persona `p.krueger@…`), for the queue view.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MANUFACTURING_CORE = "Manufacturing Core"


def custom_field_definitions() -> dict[str, list[dict]]:
	return {
		"Production Plan": [
			{
				"fieldname": "rw_production_line",
				"label": _("Fertigungslinie"),
				"fieldtype": "Link",
				"options": "Production Line",
				"insert_after": "company",
				"in_standard_filter": 1,
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "rw_planner",
				"label": _("Planer"),
				"fieldtype": "Link",
				"options": "User",
				"insert_after": "rw_production_line",
				"module": MANUFACTURING_CORE,
			},
			{
				"fieldname": "rw_raw_warehouse",
				"label": _("Rohstofflager"),
				"fieldtype": "Link",
				"options": "Warehouse",
				"description": _(
					"Lager, gegen das die Bedarfsrechnung (MRP) die Verfügbarkeit prüft (W2-Verfügbarkeit)."
				),
				"insert_after": "rw_planner",
				"module": MANUFACTURING_CORE,
			},
		],
	}


def setup_w3_planning() -> None:
	"""Create the W3-1 planning Custom Fields; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w3_planning()
