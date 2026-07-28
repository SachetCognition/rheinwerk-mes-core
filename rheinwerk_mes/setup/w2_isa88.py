"""W2-6 installer — the ISA-88 equipment-limit Custom Field (URS-W2-021 AC-2).

The ISA-88 recipe DocTypes (`ISA88 Recipe`, `ISA88 Unit Procedure`, `ISA88 Phase`) are
app-owned and ship as DocType JSON, so the only site artefact this installer creates is the
work centre's declared working-volume ceiling `rw_max_working_qty` — a Custom Field on the
anchor `Workstation`, owned by the `Recipe ISA88` module (no `status` token). The anchor
DocType is never forked.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the `patches.txt`
entry (existing sites). Idempotent — safe to re-run. Design: `docs/design/W2-isa88.md` §D4.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.recipe_isa88.scaling import WORKSTATION_LIMIT_FIELD

RECIPE_ISA88 = "Recipe ISA88"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The W2-6 Custom Field on the anchor Workstation (equipment working-volume ceiling)."""
	return {
		"Workstation": [
			{
				"fieldname": WORKSTATION_LIMIT_FIELD,
				"label": _("Max. Arbeitsmenge (kg)"),
				"description": _(
					"Maximales Arbeitsvolumen des Arbeitsplatzes je Charge. 0 = keine Grenze. "
					"Wird bei der Rezeptskalierung geprüft (URS-W2-021)."
				),
				"fieldtype": "Float",
				"precision": "3",
				"insert_after": "workstation_name",
				"module": RECIPE_ISA88,
			}
		]
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def setup_w2_isa88() -> dict[str, object]:
	"""Install every W2-6 site artefact; safe to re-run."""
	install_custom_fields()
	frappe.clear_cache()
	frappe.db.commit()
	return {"custom_field": WORKSTATION_LIMIT_FIELD}


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_isa88()
