"""Post-install wiring for the `rheinwerk_mes` app."""

import frappe
from frappe import _

from rheinwerk_mes.setup.custom_fields import install_custom_fields

MODULES = (
	"Manufacturing Core",
	"Execution Gating",
	"Genealogy",
	"Quality",
	"Warehouse",
	"Recipe ISA88",
	"Regulatory Hazmat",
	"Integration",
)


def after_install() -> None:
	"""Assert the module skeletons registered and install the anchor Custom Fields."""
	missing = [m for m in MODULES if not frappe.db.exists("Module Def", m)]
	if missing:
		frappe.throw(_("rheinwerk_mes Module sind nicht registriert: {0}").format(", ".join(missing)))
	install_custom_fields()
