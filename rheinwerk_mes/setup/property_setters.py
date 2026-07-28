"""Property Setters owned by `rheinwerk_mes` (never anchor-schema edits).

Two W0 concerns live here:

* the audit trail (URS-W0-015) — `track_changes` is asserted on every canonical
  master-data anchor, so the Frappe `Version` log records user, timestamp and
  the old→new value of each changed field;
* a helper that stamps every Property Setter with the owning module, which is
  what the `fixtures` hook in `hooks.py` filters on.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

MANUFACTURING_CORE = "Manufacturing Core"

AUDITED_DOCTYPES = ("Item", "Workstation", "BOM", "Routing", "Work Order", "Warehouse")


def set_property(
	doctype: str,
	fieldname: str | None,
	property_name: str,
	value: str,
	property_type: str,
	module: str = MANUFACTURING_CORE,
	for_doctype: bool = False,
) -> str:
	"""Create/replace a Property Setter and attribute it to a `rheinwerk_mes` module."""
	setter = make_property_setter(
		doctype,
		fieldname,
		property_name,
		value,
		property_type,
		for_doctype=for_doctype,
		validate_fields_for_doctype=False,
	)
	frappe.db.set_value("Property Setter", setter.name, "module", module)
	return setter.name


def install_audit_trail() -> list[str]:
	"""Guarantee document versioning on the canonical master-data anchors."""
	enabled = []
	for doctype in AUDITED_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		# Asserted unconditionally, even where the substrate already tracks changes: the
		# audit trail is a MES requirement and must not depend on an upstream default.
		set_property(doctype, None, "track_changes", "1", "Check", for_doctype=True)
		enabled.append(doctype)
	frappe.clear_cache()
	return enabled
