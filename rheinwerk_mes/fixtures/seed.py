"""Programme fixture seeding (idempotent).

Seeds the minimal shared programme fixtures the W1 acceptance suites and the local demo
stack start from:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* UoM Kg and the item groups Raw Material / Products
* items RW-CHM-0001 … RW-CHM-0003
* warehouses "RM Lager Nord" and "FG Lager Süd"
* production line LINE-1
* BOM-RW-CHM-0003-001 (anchor naming), governed and Accepted (`gov_state`, W1-4)
* production orders PO-2026-0001 (500 kg) and PO-2026-0002 (200 kg) on LINE-1

Run with::

    bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all
"""

from __future__ import annotations

import frappe
from frappe.model.naming import NamingSeries

WORK_ORDER_SERIES = "PO-.YYYY.-.####."

COMPANY = "Rheinwerk Chemie GmbH"
COMPANY_ABBR = "RWC"

ITEMS = (
	{"item_code": "RW-CHM-0001", "item_name": "Rheinol 40 Basisharz", "item_group": "Raw Material"},
	{"item_code": "RW-CHM-0002", "item_name": "Additiv K7", "item_group": "Raw Material"},
	{"item_code": "RW-CHM-0003", "item_name": "Rheinol 40 Compound", "item_group": "Products"},
)

WAREHOUSES = ("RM Lager Nord", "FG Lager Süd")

PRODUCTION_LINE = "LINE-1"

# 100 kg of compound = 80 kg base resin + 20 kg additive.
BOM_SPEC = {
	"item": "RW-CHM-0003",
	"quantity": 100.0,
	"items": (
		{"item_code": "RW-CHM-0001", "qty": 80.0},
		{"item_code": "RW-CHM-0002", "qty": 20.0},
	),
}

PRODUCTION_ORDERS = (
	{
		"name": "PO-2026-0001",
		"qty": 500.0,
		"planned_start_date": "2026-02-02 06:00:00",
		"planned_end_date": "2026-02-04 14:00:00",
	},
	{
		"name": "PO-2026-0002",
		"qty": 200.0,
		"planned_start_date": "2026-03-10 06:00:00",
		"planned_end_date": "2026-03-12 14:00:00",
	},
)


def _complete_setup_wizard() -> None:
	"""Run the ERPNext setup wizard once so substrate defaults (warehouse types, accounts,
	stock settings) exist before fixtures are seeded."""
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
	return COMPANY


def seed_uoms() -> None:
	if not frappe.db.exists("UOM", "Kg"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Kg", "must_be_whole_number": 0}).insert(
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
		if not frappe.db.exists("Item", spec["item_code"]):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": spec["item_code"],
					"item_name": spec["item_name"],
					"item_group": spec["item_group"],
					"stock_uom": "Kg",
					"is_stock_item": 1,
					"include_item_in_manufacturing": 1,
				}
			).insert(ignore_permissions=True)
		seeded.append(spec["item_code"])
	return seeded


def seed_warehouses() -> list[str]:
	seeded = []
	for warehouse_name in WAREHOUSES:
		name = f"{warehouse_name} - {COMPANY_ABBR}"
		if not frappe.db.exists("Warehouse", name):
			frappe.get_doc(
				{"doctype": "Warehouse", "warehouse_name": warehouse_name, "company": COMPANY}
			).insert(ignore_permissions=True)
		seeded.append(name)
	return seeded


def seed_production_lines() -> list[str]:
	if not frappe.db.exists("Production Line", PRODUCTION_LINE):
		frappe.get_doc(
			{
				"doctype": "Production Line",
				"production_line_name": PRODUCTION_LINE,
				"company": COMPANY,
			}
		).insert(ignore_permissions=True)
	return [PRODUCTION_LINE]


def seed_bom() -> str:
	"""Anchor `BOM` for the compound; anchor naming yields BOM-RW-CHM-0003-001."""
	existing = frappe.db.get_value("BOM", {"item": BOM_SPEC["item"], "docstatus": 1}, "name", order_by="name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": BOM_SPEC["item"],
			"company": COMPANY,
			"quantity": BOM_SPEC["quantity"],
			"currency": "EUR",
			"is_active": 1,
			"is_default": 1,
			"with_operations": 0,
			"rm_cost_as_per": "Valuation Rate",
		}
	)
	for row in BOM_SPEC["items"]:
		doc.append("items", {"item_code": row["item_code"], "qty": row["qty"]})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def seed_recipe_governance(bom_no: str) -> str:
	"""W1-4 fixture: the compound recipe governed and Accepted (`gov_state`)."""
	from rheinwerk_mes.recipe_isa88.governance import ACCEPTED

	frappe.db.set_value("BOM", bom_no, "gov_state", ACCEPTED, update_modified=False)
	return ACCEPTED


def _reset_work_order_series() -> None:
	"""Make the first seeded order land on PO-2026-0001 on a fresh site; a site that already
	issued numbers from this prefix keeps its counter."""
	series = NamingSeries(WORK_ORDER_SERIES)
	prefix = series.get_prefix()
	if not frappe.db.exists("Work Order", {"name": ("like", f"{prefix}%")}):
		series.update_counter(0)


def seed_production_orders(bom_no: str) -> list[str]:
	"""Anchor `Work Order`s PO-2026-0001/0002 with the CDM-02 extension fields populated."""
	_reset_work_order_series()
	seeded = []
	for spec in PRODUCTION_ORDERS:
		if frappe.db.exists("Work Order", spec["name"]):
			seeded.append(spec["name"])
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Work Order",
				"naming_series": WORK_ORDER_SERIES,
				"company": COMPANY,
				"production_item": BOM_SPEC["item"],
				"bom_no": bom_no,
				"qty": spec["qty"],
				"stock_uom": frappe.db.get_value("Item", BOM_SPEC["item"], "stock_uom"),
				"wip_warehouse": f"RM Lager Nord - {COMPANY_ABBR}",
				"fg_warehouse": f"FG Lager Süd - {COMPANY_ABBR}",
				"planned_start_date": spec["planned_start_date"],
				"planned_end_date": spec["planned_end_date"],
				"production_line": PRODUCTION_LINE,
			}
		)
		doc.insert(ignore_permissions=True)
		seeded.append(doc.name)
	return seeded


def seed_all() -> dict:
	"""Seed every programme fixture; safe to re-run."""
	summary: dict = {"company": seed_company()}
	seed_uoms()
	seed_item_groups()
	summary["items"] = seed_items()
	summary["warehouses"] = seed_warehouses()
	summary["production_lines"] = seed_production_lines()
	summary["bom"] = seed_bom()
	summary["recipe_governance"] = seed_recipe_governance(summary["bom"])
	summary["production_orders"] = seed_production_orders(summary["bom"])
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
