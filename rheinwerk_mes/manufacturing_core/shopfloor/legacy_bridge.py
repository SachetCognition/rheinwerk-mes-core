"""Legacy bridge affordance on renamed fields (W1-7 · URS-W1-022).

During the consolidation programme every field whose name changed from the legacy
vocabulary offers its old name on hover ("was: Technology"), so a Qcadoo or OFBiz veteran
recognises the field before reading the new label (design skill § "Interaction rules —
Legacy bridge affordance"). The affordance is removable after cutover by switching the
global default flag off — `set_enabled(False)` also strips the hints from the Desk form.

Legacy vocabulary source: dossier ch. 3.1 §B.1 (Qcadoo entity names); the mapping mirrors
`docs/canonical-model/README.md` CDM-02/CDM-04 renames. No legacy code is ported — only
the names people still say on the shop floor.
"""

from __future__ import annotations

import frappe
from frappe import _

#: Global default holding the feature flag; removable after cutover.
FLAG_KEY = "rw_legacy_bridge_enabled"

#: (doctype, fieldname) → legacy name, exactly as the legacy system spelled it.
LEGACY_FIELD_NAMES: dict[tuple[str, str], str] = {
	("Work Order", "bom_no"): "Technology",
	("Work Order", "exec_state"): "Order state",
	("Work Order", "qty"): "Plannedded quantity",
	("Work Order", "production_item"): "Product",
	("Work Order", "planned_start_date"): "Date from",
	("Work Order", "planned_end_date"): "Date to",
	("Job Card", "operation"): "Technology operation component",
	("Job Card", "workstation"): "Workstation",
	("Job Card", "total_completed_qty"): "Done quantity",
	("Job Card", "time_logs"): "Production tracking",
	("BOM", "name"): "Technology",
	("Batch", "batch_id"): "Resource batch",
}

# `Plannedded quantity` is the literal Qcadoo label (typo included) — kept verbatim so the
# hover matches what veterans read for twenty years.


def is_enabled() -> bool:
	"""True while the migration-programme affordance is switched on."""
	value = frappe.defaults.get_global_default(FLAG_KEY)
	return str(value) in ("1", "True", "true")


def set_enabled(enabled: bool) -> bool:
	"""Switch the affordance on or off and (re)apply it to the Desk forms."""
	frappe.defaults.set_global_default(FLAG_KEY, "1" if enabled else "0")
	apply_hints()
	frappe.clear_cache()
	return is_enabled()


def hint_text(legacy_name: str) -> str:
	"""The hover text shown on a renamed field."""
	return _("früher: {0}").format(legacy_name)


def legacy_hint(doctype: str, fieldname: str) -> str | None:
	"""Hover text for one field, or `None` when there is none / the flag is off."""
	if not is_enabled():
		return None
	legacy_name = LEGACY_FIELD_NAMES.get((doctype, fieldname))
	return hint_text(legacy_name) if legacy_name else None


@frappe.whitelist()
def legacy_hints(doctype: str) -> dict[str, str]:
	"""Every hover hint for `doctype` — consumed by the shop-floor page and Desk JS."""
	if not is_enabled():
		return {}
	return {
		field: hint_text(legacy_name)
		for (dt, field), legacy_name in LEGACY_FIELD_NAMES.items()
		if dt == doctype
	}


def apply_hints() -> int:
	"""Write the hints onto the anchor fields as Property Setters (or clear them).

	Property Setters keep the anchor DocTypes unforked; clearing sets an empty description
	so nothing of the affordance survives the flag being switched off.
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	enabled = is_enabled()
	written = 0
	for (doctype, fieldname), legacy_name in LEGACY_FIELD_NAMES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).get_field(fieldname):
			continue
		make_property_setter(
			doctype,
			fieldname,
			"description",
			hint_text(legacy_name) if enabled else "",
			"Text",
			validate_fields_for_doctype=False,
		)
		written += 1
	return written
