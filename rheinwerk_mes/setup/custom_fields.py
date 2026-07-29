"""Custom Field definitions extending the ERPNext anchor DocTypes.

The anchors (here: `Item`) are never forked — every canonical-model extension
lands as a Custom Field owned by a `rheinwerk_mes` module, so
`bench --site … export-fixtures` and the app's `fixtures` hook carry them and
the substrate stays byte-identical to upstream.

Field-level mapping: `docs/canonical-model/item-master.md` (CDM-09).
Labels are German-first and passed through `frappe._()`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MANUFACTURING_CORE = "Manufacturing Core"

LEGACY_REFS_FIELDNAME = "legacy_refs"


def _legacy_refs_fields(insert_after: str, module: str) -> list[dict]:
	"""The `legacy_refs` source-identifier mapping block (URS-W0-003 AC-2)."""
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
	"""All canonical master-data Custom Fields, keyed by anchor DocType."""
	return {"Item": _legacy_refs_fields("barcodes", MANUFACTURING_CORE)}


def install_custom_fields() -> None:
	"""Create/refresh every Custom Field; safe to re-run."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	frappe.clear_cache()
