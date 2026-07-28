"""Post-install wiring for the `rheinwerk_mes` app."""

import frappe
from frappe import _

from rheinwerk_mes.setup.w0 import setup_w0
from rheinwerk_mes.setup.w1_exec_state import setup_w1_exec_state
from rheinwerk_mes.setup.w1_warehouse import setup_w1_warehouse

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
	"""Assert the module skeletons registered (URS-W0-001 AC-1) and apply W0 defaults."""
	missing = [m for m in MODULES if not frappe.db.exists("Module Def", m)]
	if missing:
		frappe.throw(_("rheinwerk_mes Module sind nicht registriert: {0}").format(", ".join(missing)))
	setup_w0()
	setup_w1_exec_state()
	setup_w1_warehouse()
