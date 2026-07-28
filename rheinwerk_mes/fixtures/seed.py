"""Programme fixture seeding (idempotent).

Seeds the shared programme fixtures named in `docs/test/TST-W0-foundation.md` §1
so that every wave's integration/acceptance suite and the local demo stack start
from the same data:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* UoMs kg / sack / pail with item-level conversions
* items RW-CHM-0001 … RW-CHM-0003
* warehouses "RM Lager Nord" (FEFO) and "FG Lager Süd" (FIFO)
* work centres LINE-1/MIX-01 and LINE-1/FILL-01
* personas T. Schmid, P. Krüger, W. Braun, Q. Fischer, O. Weber, B. Vogel

Run with::

    bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all

Wave children extend this module (never replace it) as their canonical entities
and custom fields land.
"""

from __future__ import annotations

import frappe

COMPANY = "Rheinwerk Chemie GmbH"
COMPANY_ABBR = "RWC"

ITEMS = (
	{
		"item_code": "RW-CHM-0001",
		"item_name": "Rheinol 40 Basisharz",
		"item_group": "Raw Material",
		"stock_uom": "Kg",
		"pack_uom": "Sack",
		"pack_factor": 25.0,
		"has_batch_no": 1,
		"has_expiry_date": 1,
		"shelf_life_in_days": 365,
	},
	{
		"item_code": "RW-CHM-0002",
		"item_name": "Additiv K7",
		"item_group": "Raw Material",
		"stock_uom": "Kg",
		"pack_uom": "Pail",
		"pack_factor": 5.0,
		"has_batch_no": 1,
		"has_expiry_date": 1,
		"shelf_life_in_days": 180,
	},
	{
		"item_code": "RW-CHM-0003",
		"item_name": "Rheinol 40 Compound",
		"item_group": "Products",
		"stock_uom": "Kg",
		"pack_uom": None,
		"pack_factor": None,
		"has_batch_no": 1,
		"has_expiry_date": 1,
		"shelf_life_in_days": 540,
	},
)

WAREHOUSES = (
	{"warehouse_name": "RM Lager Nord", "disposal_method": "FEFO"},
	{"warehouse_name": "FG Lager Süd", "disposal_method": "FIFO"},
)

WORK_CENTRES = (
	{"workstation_name": "MIX-01", "production_line": "LINE-1"},
	{"workstation_name": "FILL-01", "production_line": "LINE-1"},
)

PERSONAS = (
	{
		"email": "t.schmid@rheinwerk-chemie.example",
		"first_name": "T.",
		"last_name": "Schmid",
		"roles": ["Item Manager", "Manufacturing Manager"],
	},
	{
		"email": "p.krueger@rheinwerk-chemie.example",
		"first_name": "P.",
		"last_name": "Krüger",
		"roles": ["Manufacturing User"],
	},
	{
		"email": "w.braun@rheinwerk-chemie.example",
		"first_name": "W.",
		"last_name": "Braun",
		"roles": ["Stock User"],
	},
	{
		"email": "q.fischer@rheinwerk-chemie.example",
		"first_name": "Q.",
		"last_name": "Fischer",
		"roles": ["Quality Manager"],
	},
	{
		"email": "o.weber@rheinwerk-chemie.example",
		"first_name": "O.",
		"last_name": "Weber",
		"roles": ["Manufacturing User"],
	},
	{
		"email": "b.vogel@rheinwerk-chemie.example",
		"first_name": "B.",
		"last_name": "Vogel",
		"roles": ["Manufacturing User"],
	},
)


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).get_field(fieldname))


def _complete_setup_wizard() -> None:
	"""Run the ERPNext setup wizard once, so substrate defaults (warehouse types,
	accounts, stock settings) exist before fixtures are seeded."""
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"country": "Germany",
			"timezone": "Europe/Berlin",
			"currency": "EUR",
			"company_name": COMPANY,
			"company_abbr": COMPANY_ABBR,
			"chart_of_accounts": "Standard",
			"fy_start_date": "2026-01-01",
			"fy_end_date": "2026-12-31",
			"full_name": "Administrator",
			"email": "admin@rheinwerk-chemie.example",
			"setup_demo": 0,
		}
	)
	frappe.db.commit()


def seed_company() -> str:
	if not frappe.db.get_single_value("System Settings", "setup_complete"):
		_complete_setup_wizard()
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"default_currency": "EUR",
				"country": "Germany",
			}
		).insert(ignore_permissions=True)
	frappe.db.set_single_value("Global Defaults", "default_company", COMPANY)
	system_settings = frappe.get_single("System Settings")
	system_settings.date_format = "dd.mm.yyyy"
	system_settings.country = "Germany"
	system_settings.time_zone = "Europe/Berlin"
	system_settings.save(ignore_permissions=True)
	return COMPANY


def seed_uoms() -> None:
	for uom, must_be_whole in (("Kg", 0), ("Sack", 1), ("Pail", 1)):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom, "must_be_whole_number": must_be_whole}).insert(
				ignore_permissions=True
			)


def seed_item_groups() -> None:
	for group in ("Raw Material", "Products"):
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": group,
					"parent_item_group": "All Item Groups",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def seed_items() -> list[str]:
	seeded = []
	for spec in ITEMS:
		if frappe.db.exists("Item", spec["item_code"]):
			seeded.append(spec["item_code"])
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": spec["item_code"],
				"item_name": spec["item_name"],
				"item_group": spec["item_group"],
				"stock_uom": spec["stock_uom"],
				"is_stock_item": 1,
				"has_batch_no": spec["has_batch_no"],
				"has_expiry_date": spec["has_expiry_date"],
				"shelf_life_in_days": spec["shelf_life_in_days"],
				"create_new_batch": 1,
			}
		)
		if spec["pack_uom"]:
			doc.append("uoms", {"uom": spec["pack_uom"], "conversion_factor": spec["pack_factor"]})
		doc.insert(ignore_permissions=True)
		seeded.append(doc.name)
	return seeded


def seed_warehouses() -> list[str]:
	seeded = []
	for spec in WAREHOUSES:
		name = f"{spec['warehouse_name']} - {COMPANY_ABBR}"
		if not frappe.db.exists("Warehouse", name):
			doc = frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": spec["warehouse_name"],
					"company": COMPANY,
				}
			)
			if _has_field("Warehouse", "disposal_method"):
				doc.disposal_method = spec["disposal_method"]
			doc.insert(ignore_permissions=True)
			name = doc.name
		seeded.append(name)
	return seeded


def seed_work_centres() -> list[str]:
	seeded = []
	for spec in WORK_CENTRES:
		if not frappe.db.exists("Workstation", spec["workstation_name"]):
			doc = frappe.get_doc(
				{
					"doctype": "Workstation",
					"workstation_name": spec["workstation_name"],
					"company": COMPANY,
				}
			)
			if _has_field("Workstation", "production_line"):
				doc.production_line = spec["production_line"]
			doc.insert(ignore_permissions=True)
		seeded.append(spec["workstation_name"])
	return seeded


def seed_personas() -> list[str]:
	seeded = []
	for spec in PERSONAS:
		if not frappe.db.exists("User", spec["email"]):
			doc = frappe.get_doc(
				{
					"doctype": "User",
					"email": spec["email"],
					"first_name": spec["first_name"],
					"last_name": spec["last_name"],
					"language": "de",
					"send_welcome_email": 0,
				}
			)
			doc.insert(ignore_permissions=True)
			for role in spec["roles"]:
				if frappe.db.exists("Role", role):
					doc.add_roles(role)
		seeded.append(spec["email"])
	return seeded


def seed_all() -> dict:
	"""Seed every programme fixture; safe to re-run."""
	summary = {
		"company": seed_company(),
	}
	seed_uoms()
	seed_item_groups()
	summary["items"] = seed_items()
	summary["warehouses"] = seed_warehouses()
	summary["work_centres"] = seed_work_centres()
	summary["personas"] = seed_personas()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
