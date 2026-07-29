"""Programme fixture seeding (idempotent).

Seeds the shared programme fixtures named in `docs/test/TST-W0-foundation.md` §1
that the canonical recipe base needs (URS-W0-006), so that every wave's
integration/acceptance suite and the local demo stack start from the same data:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* UoMs kg / sack / pail with item-level conversions
* items RW-CHM-0001 … RW-CHM-0003
* work centres LINE-1/MIX-01 and LINE-1/FILL-01 with the MIX and FILL operations
* routing RT-COMPOUND-01 and BOM-RW-CHM-0003-001 on the anchor DocTypes

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

WORK_CENTRES = (
	{"workstation_name": "MIX-01", "production_line": "LINE-1", "division": "Mischerei"},
	{"workstation_name": "FILL-01", "production_line": "LINE-1", "division": "Abfüllung"},
)

OPERATIONS = (
	{"operation": "MIX", "workstation": "MIX-01", "time_in_mins": 90.0},
	{"operation": "FILL", "workstation": "FILL-01", "time_in_mins": 45.0},
)

ROUTING = "RT-COMPOUND-01"

# 100 kg of compound = 80 kg base resin + 20 kg additive (docs/test/TST-W0-foundation.md §1).
BOM_SPEC = {
	"item": "RW-CHM-0003",
	"quantity": 100.0,
	"routing": ROUTING,
	"items": (
		{"item_code": "RW-CHM-0001", "qty": 80.0},
		{"item_code": "RW-CHM-0002", "qty": 20.0},
	),
}


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).get_field(fieldname))


def _backfill(doctype: str, name: str, values: dict[str, str]) -> None:
	"""Fill still-empty extension fields on a record seeded before they existed.

	Seeding is idempotent but must not silently leave a record without the
	extension values a later wave's custom fields introduced.
	"""
	pending = {
		fieldname: value
		for fieldname, value in values.items()
		if _has_field(doctype, fieldname) and not frappe.db.get_value(doctype, name, fieldname)
	}
	if not pending:
		return
	doc = frappe.get_doc(doctype, name)
	doc.update(pending)
	doc.save(ignore_permissions=True)


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


def seed_work_centres() -> list[str]:
	"""Anchor `Workstation` records the routing operations are performed on.

	The `production_line` / `division` links are custom fields a sibling W0 slice
	adds; they are populated when present and backfilled once they land.
	"""
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
			if _has_field("Workstation", "division"):
				doc.division = spec["division"]
			doc.insert(ignore_permissions=True)
		else:
			_backfill(
				"Workstation",
				spec["workstation_name"],
				{"production_line": spec["production_line"], "division": spec["division"]},
			)
		seeded.append(spec["workstation_name"])
	return seeded


def seed_operations() -> list[str]:
	"""Routing operations MIX and FILL on the LINE-1 work centres."""
	seeded = []
	for spec in OPERATIONS:
		if not frappe.db.exists("Operation", spec["operation"]):
			frappe.get_doc(
				{
					"doctype": "Operation",
					"__newname": spec["operation"],
					"workstation": spec["workstation"],
				}
			).insert(ignore_permissions=True)
		seeded.append(spec["operation"])
	return seeded


def seed_routing() -> str:
	"""Anchor `Routing` RT-COMPOUND-01: mix at MIX-01, then fill at FILL-01."""
	if frappe.db.exists("Routing", ROUTING):
		return ROUTING
	doc = frappe.get_doc({"doctype": "Routing", "routing_name": ROUTING, "disabled": 0})
	for spec in OPERATIONS:
		doc.append(
			"operations",
			{
				"operation": spec["operation"],
				"workstation": spec["workstation"],
				"time_in_mins": spec["time_in_mins"],
			},
		)
	doc.insert(ignore_permissions=True)
	return doc.name


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
			"with_operations": 1,
			"routing": BOM_SPEC["routing"],
			"rm_cost_as_per": "Valuation Rate",
		}
	)
	for row in BOM_SPEC["items"]:
		doc.append("items", {"item_code": row["item_code"], "qty": row["qty"]})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def seed_all() -> dict:
	"""Seed every programme fixture; safe to re-run."""
	summary = {
		"company": seed_company(),
	}
	seed_uoms()
	seed_item_groups()
	summary["items"] = seed_items()
	summary["work_centres"] = seed_work_centres()
	summary["operations"] = seed_operations()
	summary["routing"] = seed_routing()
	summary["bom"] = seed_bom()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
