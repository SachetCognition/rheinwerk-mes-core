"""Post-install wiring for the `rheinwerk_mes` app."""

import frappe

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
	"""Assert the eight module skeletons registered (URS-W0-001 AC-1).

	Frappe creates a `Module Def` per line of `modules.txt` during install; if any
	is missing the install is incomplete, so fail loudly rather than leave a
	half-registered app on the site.
	"""
	missing = [m for m in MODULES if not frappe.db.exists("Module Def", m)]
	if missing:
		frappe.throw(f"rheinwerk_mes modules not registered: {', '.join(missing)}")
