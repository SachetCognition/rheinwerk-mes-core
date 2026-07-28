"""Programme fixture seeding (idempotent).

Seeds the shared programme fixtures named in `docs/test/TST-W0-foundation.md` §1
so that every wave's integration/acceptance suite and the local demo stack start
from the same data:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* UoMs kg / sack / pail with item-level conversions
* items RW-CHM-0001 … RW-CHM-0003
* warehouses "RM Lager Nord" (FEFO) and "FG Lager Süd" (FIFO)
* plant-area divisions and production line LINE-1
* work centres LINE-1/MIX-01 and LINE-1/FILL-01
* routing RT-COMPOUND-01 and BOM-RW-CHM-0003-001, governed and Accepted (W1-4)
* production orders PO-2026-0001 (500 kg RW-CHM-0003 on LINE-1) and PO-2026-0002 (200 kg)
* `legacy_refs` source-identifier examples incl. the Qcadoo trigger number 000123/2025
* personas T. Schmid, P. Krüger, W. Braun, Q. Fischer, O. Weber, B. Vogel

Run with::

    bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all

Wave children extend this module (never replace it) as their canonical entities
and custom fields land.
"""

from __future__ import annotations

import frappe
from frappe.model.naming import NamingSeries

from rheinwerk_mes.setup.naming import WORK_ORDER_SERIES

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

DIVISIONS = (
	{"division_name": "Werk Nord", "parent_division": None, "is_group": 1},
	{"division_name": "Mischerei", "parent_division": "Werk Nord", "is_group": 0},
	{"division_name": "Abfüllung", "parent_division": "Werk Nord", "is_group": 0},
)

PRODUCTION_LINES = ({"production_line_name": "LINE-1", "division": "Werk Nord"},)

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

PRODUCTION_ORDER = {
	"name": "PO-2026-0001",
	"production_item": "RW-CHM-0003",
	"qty": 500.0,
	"production_line": "LINE-1",
	"wip_warehouse": "RM Lager Nord",
	"fg_warehouse": "FG Lager Süd",
	"planned_start_date": "2026-02-02 06:00:00",
}

# Second order used by the W1 state-machine and gating suites (TST-W1 §1).
SECOND_PRODUCTION_ORDER = {
	"name": "PO-2026-0002",
	"production_item": "RW-CHM-0003",
	"qty": 200.0,
	"production_line": "LINE-1",
	"wip_warehouse": "RM Lager Nord",
	"fg_warehouse": "FG Lager Süd",
	"planned_start_date": "2026-03-10 06:00:00",
}

# Source-system identifiers preserved out of the primary key (URS-W0-003, URS-W0-014).
LEGACY_REFS = (
	{
		"doctype": "Item",
		"name": "RW-CHM-0001",
		"refs": (
			{
				"source_system": "Qcadoo",
				"source_entity": "basic_product",
				"source_identifier": "P-000123",
			},
			{
				"source_system": "OFBiz",
				"source_entity": "Product",
				"source_identifier": "RHEINOL-40-BASE",
			},
		),
	},
	{
		"doctype": "Item",
		"name": "RW-CHM-0002",
		"refs": (
			{
				"source_system": "Qcadoo",
				"source_entity": "basic_product",
				"source_identifier": "P-000124",
			},
		),
	},
	{
		"doctype": "Item",
		"name": "RW-CHM-0003",
		"refs": (
			{
				"source_system": "ERPNext Legacy",
				"source_entity": "Item",
				"source_identifier": "COMPOUND-40",
			},
		),
	},
	{
		"doctype": "Work Order",
		"name": PRODUCTION_ORDER["name"],
		"refs": (
			{
				"source_system": "Qcadoo",
				"source_entity": "orders_order",
				"source_identifier": "000123/2025",
			},
		),
	},
)

PERSONAS = (
	{
		"email": "t.schmid@rheinwerk-chemie.example",
		"first_name": "T.",
		"last_name": "Schmid",
		"roles": ["Rheinwerk Technologist", "Item Manager", "Manufacturing Manager"],
	},
	{
		"email": "p.krueger@rheinwerk-chemie.example",
		"first_name": "P.",
		"last_name": "Krüger",
		# Planner: read-only on master data, owns production orders (URS-W0-017).
		"roles": ["Rheinwerk Planner"],
	},
	{
		"email": "w.braun@rheinwerk-chemie.example",
		"first_name": "W.",
		"last_name": "Braun",
		# Warehouse clerk: read-only on master data (URS-W0-017).
		"roles": ["Rheinwerk Warehouse Clerk", "Stock User"],
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
		else:
			_backfill("Warehouse", name, {"disposal_method": spec["disposal_method"]})
		seeded.append(name)
	return seeded


def seed_divisions() -> list[str]:
	"""Plant-area tree backing the Work Centre `division` link (CDM-08)."""
	if not frappe.db.exists("DocType", "Division"):
		return []
	seeded = []
	for spec in DIVISIONS:
		if not frappe.db.exists("Division", spec["division_name"]):
			frappe.get_doc(
				{
					"doctype": "Division",
					"division_name": spec["division_name"],
					"parent_division": spec["parent_division"],
					"is_group": spec["is_group"],
					"company": COMPANY,
				}
			).insert(ignore_permissions=True)
		seeded.append(spec["division_name"])
	return seeded


def seed_production_lines() -> list[str]:
	"""Line grouping addressed by planners (CDM-08)."""
	if not frappe.db.exists("DocType", "Production Line"):
		return []
	seeded = []
	for spec in PRODUCTION_LINES:
		if not frappe.db.exists("Production Line", spec["production_line_name"]):
			frappe.get_doc(
				{
					"doctype": "Production Line",
					"production_line_name": spec["production_line_name"],
					"division": spec["division"],
					"company": COMPANY,
				}
			).insert(ignore_permissions=True)
		seeded.append(spec["production_line_name"])
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


def seed_recipe_governance(bom_no: str) -> str | None:
	"""W1-4 fixture: the compound recipe governed and Accepted (URS-W1-014, TC-W1-015).

	The record walks the real lifecycle Draft → Checked → Accepted, so the seeded state is
	produced by the same validators and transition rules the technologist uses. Skipped when
	the `Recipe Governance` DocType is not installed yet.
	"""
	if not frappe.db.exists("DocType", "Recipe Governance"):
		return None
	from rheinwerk_mes.recipe_isa88.governance import ACCEPTED, CHECKED, transition

	name = frappe.db.get_value("Recipe Governance", {"bom": bom_no}, "name")
	if not name:
		doc = frappe.get_doc({"doctype": "Recipe Governance", "bom": bom_no, "routing": ROUTING}).insert(
			ignore_permissions=True
		)
		name = doc.name
	if frappe.db.get_value("Recipe Governance", name, "gov_state") not in (ACCEPTED, "Outdated", "Declined"):
		transition(name, CHECKED)
		transition(name, ACCEPTED)
	return name


def seed_production_order(bom_no: str) -> str:
	"""Anchor `Work Order` PO-2026-0001 with the CDM-02 extension fields populated."""
	if frappe.db.exists("Work Order", PRODUCTION_ORDER["name"]):
		return PRODUCTION_ORDER["name"]
	_reset_work_order_series()
	doc = frappe.get_doc(
		{
			"doctype": "Work Order",
			"naming_series": WORK_ORDER_SERIES,
			"company": COMPANY,
			"production_item": PRODUCTION_ORDER["production_item"],
			"bom_no": bom_no,
			"qty": PRODUCTION_ORDER["qty"],
			# Mass in kg on every W0 screen (URS-W0-016); the anchor default is Nos.
			"stock_uom": frappe.db.get_value("Item", PRODUCTION_ORDER["production_item"], "stock_uom"),
			"wip_warehouse": f"{PRODUCTION_ORDER['wip_warehouse']} - {COMPANY_ABBR}",
			"fg_warehouse": f"{PRODUCTION_ORDER['fg_warehouse']} - {COMPANY_ABBR}",
			"planned_start_date": PRODUCTION_ORDER["planned_start_date"],
		}
	)
	if _has_field("Work Order", "production_line"):
		doc.production_line = PRODUCTION_ORDER["production_line"]
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_second_production_order(bom_no: str) -> str:
	"""Anchor `Work Order` PO-2026-0002 (W1 fixtures — TST-W1-production-core §1)."""
	if frappe.db.exists("Work Order", SECOND_PRODUCTION_ORDER["name"]):
		return SECOND_PRODUCTION_ORDER["name"]
	doc = frappe.get_doc(
		{
			"doctype": "Work Order",
			"naming_series": WORK_ORDER_SERIES,
			"company": COMPANY,
			"production_item": SECOND_PRODUCTION_ORDER["production_item"],
			"bom_no": bom_no,
			"qty": SECOND_PRODUCTION_ORDER["qty"],
			"stock_uom": frappe.db.get_value("Item", SECOND_PRODUCTION_ORDER["production_item"], "stock_uom"),
			"wip_warehouse": f"{SECOND_PRODUCTION_ORDER['wip_warehouse']} - {COMPANY_ABBR}",
			"fg_warehouse": f"{SECOND_PRODUCTION_ORDER['fg_warehouse']} - {COMPANY_ABBR}",
			"planned_start_date": SECOND_PRODUCTION_ORDER["planned_start_date"],
		}
	)
	if _has_field("Work Order", "production_line"):
		doc.production_line = SECOND_PRODUCTION_ORDER["production_line"]
	doc.insert(ignore_permissions=True)
	return doc.name


def _reset_work_order_series() -> None:
	"""Make the first seeded order land on PO-2026-0001 on a fresh site; a site that
	already issued numbers from this prefix keeps its counter."""
	series = NamingSeries(WORK_ORDER_SERIES)
	prefix = series.get_prefix()
	if not frappe.db.exists("Work Order", {"name": ("like", f"{prefix}%")}):
		series.update_counter(0)


def seed_legacy_refs() -> list[str]:
	"""Attach source-system identifiers, incl. the Qcadoo trigger number 000123/2025."""
	seeded = []
	for spec in LEGACY_REFS:
		if not _has_field(spec["doctype"], "legacy_refs"):
			continue
		if not frappe.db.exists(spec["doctype"], spec["name"]):
			continue
		doc = frappe.get_doc(spec["doctype"], spec["name"])
		known = {row.source_identifier for row in doc.get("legacy_refs") or []}
		missing = [ref for ref in spec["refs"] if ref["source_identifier"] not in known]
		if not missing:
			seeded.append(spec["name"])
			continue
		for ref in missing:
			doc.append("legacy_refs", ref)
		doc.save(ignore_permissions=True)
		seeded.append(spec["name"])
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
		doc = frappe.get_doc("User", spec["email"])
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
	summary["divisions"] = seed_divisions()
	summary["production_lines"] = seed_production_lines()
	summary["work_centres"] = seed_work_centres()
	summary["operations"] = seed_operations()
	summary["routing"] = seed_routing()
	summary["bom"] = seed_bom()
	summary["recipe_governance"] = seed_recipe_governance(summary["bom"])
	summary["production_order"] = seed_production_order(summary["bom"])
	summary["second_production_order"] = seed_second_production_order(summary["bom"])
	summary["legacy_refs"] = seed_legacy_refs()
	summary["personas"] = seed_personas()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
