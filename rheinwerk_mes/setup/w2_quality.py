"""W2-4/W2-5 installer — Quality Inspection extensions and the CoA (URS-W2-013…019).

Everything the quality module needs on a site is created here, idempotently, from committed
code (programme rule 1). The ERPNext `Quality Inspection` anchor is **not forked**:

* Custom Fields carry the estate's references and the QA disposition
  (`rw_work_order`, `rw_disposition`, `rw_disposition_reason`, `rw_rework_order`,
  `rw_disposition_recorded_on`) plus the unit of a quality parameter (`rw_unit`);
* two Property Setters relax the anchor's `reference_type` / `reference_name` mandatory
  flags, because an MES in-process inspection references a production order (via
  `rw_work_order`), not a stock voucher — decision D1 in `docs/design/W2-quality-coa.md`;
* the quality role gets the permissions it needs on the anchor and on the CoA.

Invoked from `after_install` (fresh site) and from `patches.txt` (existing sites).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from rheinwerk_mes.quality.disposition import DISPOSITIONS

QUALITY_MODULE = "Quality"
QUALITY_ROLE = "Quality Manager"
BUSINESS_VIEWER = "Rheinwerk Business Viewer"

COA_DOCTYPE = "CoA Certificate"


def custom_field_definitions() -> dict[str, list[dict]]:
	return {
		"Quality Inspection": [
			{
				"fieldname": "rw_work_order",
				"label": _("Fertigungsauftrag"),
				"fieldtype": "Link",
				"options": "Work Order",
				"insert_after": "bom_no",
				"in_standard_filter": 1,
				"module": QUALITY_MODULE,
			},
			{
				"fieldname": "rw_disposition_section",
				"label": _("Verwendungsentscheid"),
				"fieldtype": "Section Break",
				"insert_after": "remarks",
				"depends_on": "eval:doc.status == 'Rejected'",
				"module": QUALITY_MODULE,
			},
			{
				"fieldname": "rw_disposition",
				"label": _("Verwendungsentscheid"),
				"fieldtype": "Select",
				"options": "\n" + "\n".join(DISPOSITIONS),
				"insert_after": "rw_disposition_section",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_standard_filter": 1,
				"module": QUALITY_MODULE,
			},
			{
				"fieldname": "rw_disposition_reason",
				"label": _("Begründung des Verwendungsentscheids"),
				"fieldtype": "Small Text",
				"insert_after": "rw_disposition",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": QUALITY_MODULE,
			},
			{
				"fieldname": "rw_rework_order",
				"label": _("Nacharbeitsauftrag"),
				"fieldtype": "Link",
				"options": "Work Order",
				"insert_after": "rw_disposition_reason",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": QUALITY_MODULE,
			},
			{
				"fieldname": "rw_disposition_recorded_on",
				"label": _("Verwendungsentscheid erfasst am"),
				"fieldtype": "Datetime",
				"insert_after": "rw_rework_order",
				"read_only": 1,
				"allow_on_submit": 1,
				"module": QUALITY_MODULE,
			},
		],
		"Quality Inspection Parameter": [
			{
				"fieldname": "rw_unit",
				"label": _("Einheit"),
				"fieldtype": "Data",
				"insert_after": "parameter_group",
				"description": _("Wird in der Prüfmaske hinter dem Eingabefeld angezeigt (z. B. mPa·s)."),
				"module": QUALITY_MODULE,
			},
		],
	}


#: (doctype, fieldname, property, value) — the anchor stays untouched, only its metadata
#: is overridden. An MES inspection references a production order, not a stock voucher.
PROPERTY_SETTERS: tuple[tuple[str, str, str, str], ...] = (
	("Quality Inspection", "reference_type", "reqd", "0"),
	("Quality Inspection", "reference_name", "reqd", "0"),
)


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def install_property_setters() -> None:
	for doctype, fieldname, prop, value in PROPERTY_SETTERS:
		setter = make_property_setter(
			doctype, fieldname, prop, value, "Check", validate_fields_for_doctype=False
		)
		if setter and setter.module != QUALITY_MODULE:
			frappe.db.set_value("Property Setter", setter.name, "module", QUALITY_MODULE)


def install_permissions() -> None:
	"""Quality owns the inspections and the certificates; the business viewer reads CoAs."""
	from frappe.permissions import add_permission, update_permission_property

	for role, ptypes in (
		(QUALITY_ROLE, ("read", "write", "create", "submit", "cancel", "print", "report", "export")),
		(BUSINESS_VIEWER, ("read", "print", "report", "export")),
	):
		if not frappe.db.exists("Role", role):
			continue
		for doctype in ("Quality Inspection", COA_DOCTYPE):
			add_permission(doctype, role, 0)
			for ptype in ptypes:
				if frappe.get_meta(doctype).is_submittable or ptype not in ("submit", "cancel"):
					update_permission_property(doctype, role, 0, ptype, 1)


def setup_w2_quality() -> dict[str, object]:
	"""Install every W2-4/W2-5 site artefact; safe to re-run."""
	install_custom_fields()
	install_property_setters()
	install_permissions()
	frappe.clear_cache()
	frappe.db.commit()
	return {
		"custom_fields": sorted(custom_field_definitions()),
		"property_setters": [f"{dt}.{field}.{prop}" for dt, field, prop, _value in PROPERTY_SETTERS],
	}


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_quality()
