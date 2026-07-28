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
from frappe import _
from frappe.model.naming import NamingSeries

from rheinwerk_mes.setup.naming import WORK_ORDER_SERIES
from rheinwerk_mes.setup.w1_roles import assign_persona_roles

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

# W3-2: TJ/TPZ norms behind the realization times (URS-W3-006 AC-1). For the 500 kg
# PO-2026-0001 they give MIX = 30 + 500 × 0,6 = 330 min and FILL = 15 + 500 × 0,3 = 165 min,
# i.e. 495 min for the sequential routing.
TIME_NORMS = (
	{
		"operation": "MIX",
		"workstation": "MIX-01",
		"production_line": "LINE-1",
		"tpz_min": 30.0,
		"tj_min_per_unit": 0.6,
	},
	{
		"operation": "FILL",
		"workstation": "FILL-01",
		"production_line": "LINE-1",
		"tpz_min": 15.0,
		"tj_min_per_unit": 0.3,
	},
)

# W3-2: the LINE-1 changeover norm sequencing inserts between two orders (URS-W3-007 AC-1) —
# the 45-minute intermediate cleaning between two Rheinol 40 batches.
CHANGEOVER_NORMS = (
	{
		"production_line": "LINE-1",
		"from_item": "RW-CHM-0003",
		"to_item": "RW-CHM-0003",
		"changeover_min": 45.0,
	},
)

# W3-2: the anchor's capacity ceiling per work centre (`Workstation.production_capacity`) —
# one job at a time, so a second order in the same window is refused (URS-W3-008 AC-1).
WORK_CENTRE_CAPACITY = (
	{"workstation": "MIX-01", "production_capacity": 1},
	{"workstation": "FILL-01", "production_capacity": 1},
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

# W2-6: the ISA-88 structured variant of BOM-RW-CHM-0003-001 (URS-W2-020 AC-1). The recipe
# declares its own 500 kg nominal master batch (480 kg Basisharz + 20 kg Additiv K7); the
# anchor BOM stays the per-`quantity` material master (decision D2, docs/design/W2-isa88.md).
ISA88_RECIPE_SPEC = {
	"recipe_name": "Rheinol 40 Compound – Standardrezept",
	"batch_size": 500.0,
	"unit_procedures": (
		{
			"unit_procedure_id": "MISCHEN",
			"unit_procedure_name": "Mischen",
			"sequence": 10,
			"operation": "MIX",
			"workstation": "MIX-01",
		},
		{
			"unit_procedure_id": "ABFUELLEN",
			"unit_procedure_name": "Abfüllen",
			"sequence": 20,
			"operation": "FILL",
			"workstation": "FILL-01",
		},
	),
	"phases": (
		{
			"unit_procedure": "MISCHEN",
			"phase_name": "Dosieren Basisharz",
			"phase_type": "Dosieren",
			"sequence": 10,
			"material": "RW-CHM-0001",
			"quantity": 480.0,
			"uom": "Kg",
		},
		{
			"unit_procedure": "MISCHEN",
			"phase_name": "Dosieren Additiv",
			"phase_type": "Dosieren",
			"sequence": 20,
			"material": "RW-CHM-0002",
			"quantity": 20.0,
			"uom": "Kg",
		},
		{
			"unit_procedure": "MISCHEN",
			"phase_name": "Mischen 30 min",
			"phase_type": "Verarbeiten",
			"sequence": 30,
			"duration_min": 30.0,
		},
		{
			"unit_procedure": "ABFUELLEN",
			"phase_name": "Abfüllen Gebinde",
			"phase_type": "Abfüllen",
			"sequence": 10,
		},
	),
}

# W2-6: MIX-01 declares a 600 kg working-volume ceiling (URS-W2-021 AC-2), enough for the
# 500 kg master batch but not for a 750 kg scale.
WORKSTATION_LIMITS = ({"workstation": "MIX-01", "max_working_qty": 600.0},)

PRODUCTION_ORDER = {
	"name": "PO-2026-0001",
	"production_item": "RW-CHM-0003",
	"qty": 500.0,
	"production_line": "LINE-1",
	"wip_warehouse": "RM Lager Nord",
	"fg_warehouse": "FG Lager Süd",
	"planned_start_date": "2026-02-02 06:00:00",
	# The acceptance gate (URS-W1-005) requires a consistent planned range: end after start.
	"planned_end_date": "2026-02-04 14:00:00",
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
	"planned_end_date": "2026-03-12 14:00:00",
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

# W1-5: warehouse-scoped storage locations (URS-W1-019). Warehouse names carry the
# company abbreviation suffix once seeded.
STORAGE_LOCATIONS = ({"storage_location_name": "NORD-A-01-01", "warehouse": "RM Lager Nord", "is_group": 0},)

# W1-5: batch fixtures with expiries (FEFO/FIFO parity) and intake dates for FIFO/LIFO.
# BATCH-A-0001/0002 are RW-CHM-0001 resources exactly as the frozen FEFO characterisation
# fixture (`tests/characterisation/fixtures/warehouse_picking.json`) encodes them, so the
# site disposal path and the offline CHAR-FEFO-PICK-01 contract agree.
BATCHES = (
	{
		"batch_id": "BATCH-A-0001",
		"item": "RW-CHM-0001",
		"expiry_date": "2026-12-31",
		"manufacturing_date": "2026-01-05",
		"warehouse": "RM Lager Nord",
		"storage_location": "NORD-A-01-01",
		"qty": 500.0,
	},
	{
		"batch_id": "BATCH-A-0002",
		"item": "RW-CHM-0001",
		"expiry_date": "2026-06-30",
		"manufacturing_date": "2026-03-12",
		"warehouse": "RM Lager Nord",
		"storage_location": "NORD-A-01-01",
		"qty": 50.0,
	},
	{
		"batch_id": "BATCH-B-0001",
		"item": "RW-CHM-0002",
		"expiry_date": "2026-09-30",
		"manufacturing_date": "2026-02-10",
		"warehouse": "RM Lager Nord",
		"storage_location": None,
		"qty": 100.0,
	},
	{
		"batch_id": "BATCH-C-1001",
		"item": "RW-CHM-0003",
		"expiry_date": "2027-06-30",
		"manufacturing_date": "2026-03-01",
		"warehouse": "FG Lager Süd",
		"storage_location": None,
		"qty": 200.0,
	},
	{
		"batch_id": "BATCH-C-1002",
		"item": "RW-CHM-0003",
		"expiry_date": "2027-07-31",
		"manufacturing_date": "2026-04-15",
		"warehouse": "FG Lager Süd",
		"storage_location": None,
		"qty": 150.0,
	},
)

# W2-7: hazmat master data (URS-W2-023). Realistic German chemical-industry values: UN 1866
# is the ADR entry for resin solutions, UN 1263 for paint-related material; both are TRGS 510
# Lagerklasse 3 (entzündbare Flüssigkeiten) with CLP signal word "Gefahr". Additiv K7
# (RW-CHM-0002) deliberately carries no profile — it is the non-hazardous control the
# acceptance suite needs.
HAZMAT_PROFILES = (
	{
		"profile_name": "HAZ-RW-CHM-0001",
		"item": "RW-CHM-0001",
		"un_number": "UN 1866",
		"proper_shipping_name": "Harzlösung, entzündbar",
		"storage_class": "3",
		"water_hazard_class": "2",
		"signal_word": "Gefahr",
		"sds_reference": "SDS-RW-0001",
		"sds_version": "3.1",
		"sds_revision_date": "2026-01-15",
		"pictograms": ("GHS02", "GHS07"),
		"statements": (
			("H", "H226", "Flüssigkeit und Dampf entzündbar."),
			("H", "H336", "Kann Schläfrigkeit und Benommenheit verursachen."),
			("P", "P210", "Von Hitze, heißen Oberflächen, Funken, offenen Flammen fernhalten."),
			("P", "P261", "Einatmen von Dampf vermeiden."),
		),
		"mandatory": 1,
	},
	{
		"profile_name": "HAZ-RW-CHM-0003",
		"item": "RW-CHM-0003",
		"un_number": "UN 1263",
		"proper_shipping_name": "Farbe (entzündbar)",
		"storage_class": "3",
		"water_hazard_class": "2",
		"signal_word": "Gefahr",
		"sds_reference": "SDS-RW-0003",
		"sds_version": "1.4",
		"sds_revision_date": "2026-02-20",
		"pictograms": ("GHS02",),
		"statements": (
			("H", "H226", "Flüssigkeit und Dampf entzündbar."),
			("H", "H319", "Verursacht schwere Augenreizung."),
			("P", "P280", "Schutzhandschuhe und Augenschutz tragen."),
		),
		"mandatory": 1,
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
			"planned_end_date": PRODUCTION_ORDER["planned_end_date"],
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
			"planned_end_date": SECOND_PRODUCTION_ORDER["planned_end_date"],
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


def seed_warehouse_reservation_flags() -> None:
	"""Enable "draft makes reservation" on the fixture warehouses (URS-W1-023)."""
	if not _has_field("Warehouse", "draft_makes_reservation"):
		return
	for spec in WAREHOUSES:
		name = f"{spec['warehouse_name']} - {COMPANY_ABBR}"
		if frappe.db.exists("Warehouse", name) and not frappe.db.get_value(
			"Warehouse", name, "draft_makes_reservation"
		):
			frappe.db.set_value("Warehouse", name, "draft_makes_reservation", 1)


def seed_storage_locations() -> list[str]:
	"""Warehouse-scoped storage-location tree (URS-W1-019, e.g. NORD-A-01-01)."""
	if not frappe.db.exists("DocType", "Storage Location"):
		return []
	seeded = []
	for spec in STORAGE_LOCATIONS:
		warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
		if not frappe.db.exists("Warehouse", warehouse):
			continue
		if not frappe.db.exists("Storage Location", spec["storage_location_name"]):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"storage_location_name": spec["storage_location_name"],
					"warehouse": warehouse,
					"is_group": spec["is_group"],
					"company": COMPANY,
				}
			).insert(ignore_permissions=True)
		seeded.append(spec["storage_location_name"])
	return seeded


def _never_received(batch: str) -> bool:
	"""True when no opening receipt was ever booked for `batch`.

	The guard asks whether the batch was ever *received*, not whether it currently holds
	stock: a batch consumed down to zero — the expired lot, or the supplier lot the
	genealogy chain consumes in full — reads as empty and would be received again on every
	re-seed, inflating the warehouse fixtures without bound.
	"""
	# An inward row carries its batch either on the ledger entry itself or, when the anchor
	# bundled it, on the `Serial and Batch Bundle` of that entry — both are checked.
	received = frappe.db.sql(
		"""
		select 1
		from `tabStock Ledger Entry` sle
		left join `tabSerial and Batch Entry` sbe on sbe.parent = sle.serial_and_batch_bundle
		where sle.is_cancelled = 0
			and sle.actual_qty > 0
			and (sle.batch_no = %(batch)s or sbe.batch_no = %(batch)s)
		limit 1
		""",
		{"batch": batch},
	)
	return not received


def seed_batches() -> list[str]:
	"""Batch fixtures plus opening stock booked as batch-aware Material Receipts (URS-W1-021).

	The opening receipt posts only for a batch never received before, so re-seeding never
	double-books. The anchor ledger stays the single quantity truth.
	"""
	if not frappe.db.exists("DocType", "Storage Location"):
		# W1 warehouse schema not installed yet; nothing to seed.
		return []
	frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
	seeded = []
	for spec in BATCHES:
		warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
		if not frappe.db.exists("Warehouse", warehouse):
			continue
		if not frappe.db.exists("Batch", spec["batch_id"]):
			batch = frappe.get_doc(
				{
					"doctype": "Batch",
					"batch_id": spec["batch_id"],
					"item": spec["item"],
					"expiry_date": spec["expiry_date"],
					"manufacturing_date": spec["manufacturing_date"],
				}
			)
			if spec.get("storage_location") and _has_field("Batch", "storage_location"):
				batch.storage_location = spec["storage_location"]
			batch.insert(ignore_permissions=True)
		if _never_received(spec["batch_id"]):
			row = {
				"item_code": spec["item"],
				"qty": spec["qty"],
				"t_warehouse": warehouse,
				"uom": frappe.db.get_value("Item", spec["item"], "stock_uom"),
				"basic_rate": 2.0,
				"use_serial_batch_fields": 1,
				"batch_no": spec["batch_id"],
			}
			if spec.get("storage_location") and _has_field("Stock Entry Detail", "storage_location"):
				row["storage_location"] = spec["storage_location"]
			se = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"company": COMPANY,
					"set_posting_time": 1,
					"posting_date": spec["manufacturing_date"],
					"posting_time": "06:00:00",
					"items": [row],
				}
			)
			se.insert(ignore_permissions=True)
			se.submit()
		seeded.append(spec["batch_id"])
	return seeded


def seed_workstation_limits() -> None:
	"""W2-6: set the work centre working-volume ceilings (URS-W2-021 AC-2)."""
	if not _has_field("Workstation", "rw_max_working_qty"):
		return
	for spec in WORKSTATION_LIMITS:
		if frappe.db.exists("Workstation", spec["workstation"]) and not frappe.db.get_value(
			"Workstation", spec["workstation"], "rw_max_working_qty"
		):
			frappe.db.set_value(
				"Workstation", spec["workstation"], "rw_max_working_qty", spec["max_working_qty"]
			)


def seed_time_norms() -> list[str]:
	"""W3-2: TJ/TPZ norms per operation and work centre (URS-W3-006 AC-1).

	Idempotent; skipped when the `Operation Time Norm` DocType is not installed yet.
	"""
	if not frappe.db.exists("DocType", "Operation Time Norm"):
		return []
	seeded = []
	for spec in TIME_NORMS:
		existing = frappe.db.get_value(
			"Operation Time Norm",
			{"operation": spec["operation"], "workstation": spec["workstation"]},
			"name",
		)
		if existing:
			_backfill(
				"Operation Time Norm",
				existing,
				{"tpz_min": spec["tpz_min"], "tj_min_per_unit": spec["tj_min_per_unit"]},
			)
			seeded.append(existing)
			continue
		description = _("Rüstzeit (TPZ) und Stückzeit (TJ) nach Qcadoo-Norm für {0} auf {1}.").format(
			spec["operation"], spec["workstation"]
		)
		doc = frappe.get_doc({"doctype": "Operation Time Norm", **spec, "description": description}).insert(
			ignore_permissions=True
		)
		seeded.append(doc.name)
	return seeded


def seed_changeover_norms() -> list[str]:
	"""W3-2: the LINE-1 changeover norms used when sequencing (URS-W3-007 AC-1).

	Idempotent; skipped when the `Line Changeover Norm` DocType is not installed yet.
	"""
	if not frappe.db.exists("DocType", "Line Changeover Norm"):
		return []
	seeded = []
	for spec in CHANGEOVER_NORMS:
		existing = frappe.db.get_value(
			"Line Changeover Norm",
			{
				"production_line": spec["production_line"],
				"from_item": spec["from_item"],
				"to_item": spec["to_item"],
			},
			"name",
		)
		if existing:
			_backfill("Line Changeover Norm", existing, {"changeover_min": spec["changeover_min"]})
			seeded.append(existing)
			continue
		description = _("Zwischenreinigung {0} beim Produktwechsel {1} → {2}.").format(
			spec["production_line"], spec["from_item"], spec["to_item"]
		)
		doc = frappe.get_doc({"doctype": "Line Changeover Norm", **spec, "description": description}).insert(
			ignore_permissions=True
		)
		seeded.append(doc.name)
	return seeded


def seed_work_centre_capacity() -> None:
	"""W3-2: the anchor capacity ceiling the slot search reads (URS-W3-008 AC-1)."""
	for spec in WORK_CENTRE_CAPACITY:
		if not frappe.db.exists("Workstation", spec["workstation"]):
			continue
		if not frappe.db.get_value("Workstation", spec["workstation"], "production_capacity"):
			frappe.db.set_value(
				"Workstation", spec["workstation"], "production_capacity", spec["production_capacity"]
			)


def seed_isa88_recipe(bom_no: str) -> str | None:
	"""W2-6: the ISA-88 structured variant of BOM-RW-CHM-0003-001 (URS-W2-020 AC-1).

	Idempotent; skipped when the `ISA88 Recipe` DocType is not installed yet.
	"""
	if not frappe.db.exists("DocType", "ISA88 Recipe"):
		return None
	existing = frappe.db.get_value("ISA88 Recipe", {"bom": bom_no}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "ISA88 Recipe",
			"recipe_name": ISA88_RECIPE_SPEC["recipe_name"],
			"bom": bom_no,
			"routing": ROUTING,
			"batch_size": ISA88_RECIPE_SPEC["batch_size"],
		}
	)
	for up in ISA88_RECIPE_SPEC["unit_procedures"]:
		doc.append("unit_procedures", dict(up))
	for phase in ISA88_RECIPE_SPEC["phases"]:
		doc.append("phases", dict(phase))
	doc.insert(ignore_permissions=True)
	return doc.name


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


# --------------------------------------------------------------------------------------
# W2-1/2/3 genealogy fixture (TST-W2-traceability-quality §1)
# --------------------------------------------------------------------------------------

#: Supplier lot of Additiv K7 feeding the intermediate batch — the upstream end of the
#: multi-level trace (URS-W2-002).
SUPPLIER_BATCH = {
	"batch_id": "SUP-K7-0001",
	"item": "RW-CHM-0002",
	"expiry_date": "2026-11-30",
	"manufacturing_date": "2026-02-01",
	"warehouse": "RM Lager Nord",
	"storage_location": "NORD-A-01-01",
	# Fully consumed by the chain, so the supplier lot adds no stock to the W1 warehouse
	# fixtures the gating suites assert on.
	"qty": 20.0,
	"supplier_batch_no": "K7-4711-2026",
}

#: Quarantine location on the W1 storage-location tree (URS-W2-012).
QUARANTINE_LOCATION = {"storage_location_name": "NORD-Q-01", "warehouse": "RM Lager Nord"}

#: Batches released at seed time; everything else stays in the entry state Quarantined so
#: the fixture carries both dispositions (TC-W2-009, TC-W2-014).
RELEASED_BATCHES = (
	"BATCH-A-0001",
	"BATCH-A-0002",
	"BATCH-B-0001",
	"BATCH-C-1001",
	"BATCH-C-1002",
	"SUP-K7-0001",
)

#: (work order key, consumed rows, produced batch, produced qty, posting date). Posting
#: dates sit before the fixture expiries so the W1 expiry hard stop is not tripped while
#: seeding history (URS-W1-013).
GENEALOGY_CHAIN = (
	{
		"order": "second",
		"consume": (("RW-CHM-0002", "SUP-K7-0001", 20.0, "RM Lager Nord"),),
		"produce": ("RW-CHM-0001", "BATCH-A-0002", 20.0, "RM Lager Nord"),
		"posting_date": "2026-03-20",
	},
	{
		"order": "first",
		"consume": (
			("RW-CHM-0001", "BATCH-A-0001", 480.0, "RM Lager Nord"),
			("RW-CHM-0001", "BATCH-A-0002", 20.0, "RM Lager Nord"),
		),
		"produce": ("RW-CHM-0003", "BATCH-C-1001", 500.0, "FG Lager Süd"),
		"posting_date": "2026-04-01",
	},
	{
		"order": "third",
		"consume": (("RW-CHM-0001", "BATCH-A-0002", 10.0, "RM Lager Nord"),),
		"produce": ("RW-CHM-0003", "BATCH-C-1002", 10.0, "FG Lager Süd"),
		"posting_date": "2026-04-15",
	},
)


def seed_supplier_batch() -> str | None:
	"""Supplier lot SUP-K7-0001 incl. its supplier batch number (URS-W2-005)."""
	if not _has_field("Batch", "qa_state"):
		return None
	spec = SUPPLIER_BATCH
	warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
	if not frappe.db.exists("Batch", spec["batch_id"]):
		batch = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": spec["batch_id"],
				"item": spec["item"],
				"expiry_date": spec["expiry_date"],
				"manufacturing_date": spec["manufacturing_date"],
				"supplier_batch_no": spec["supplier_batch_no"],
				"qty_original": spec["qty"],
			}
		)
		if _has_field("Batch", "storage_location"):
			batch.storage_location = spec["storage_location"]
		batch.insert(ignore_permissions=True)
	if _never_received(spec["batch_id"]):
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": COMPANY,
				"set_posting_time": 1,
				"posting_date": spec["manufacturing_date"],
				"posting_time": "06:00:00",
				"items": [
					{
						"item_code": spec["item"],
						"qty": spec["qty"],
						"t_warehouse": warehouse,
						"uom": frappe.db.get_value("Item", spec["item"], "stock_uom"),
						"basic_rate": 3.0,
						"use_serial_batch_fields": 1,
						"batch_no": spec["batch_id"],
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()
	return spec["batch_id"]


def seed_hazmat_profiles() -> list[str]:
	"""W2-7: hazmat profiles for RW-CHM-0001/0003 linked to their items (URS-W2-023 AC-1)."""
	from rheinwerk_mes.regulatory_hazmat.profiles import ITEM_MANDATORY_FIELD, ITEM_PROFILE_FIELD

	if not _has_field("Item", ITEM_PROFILE_FIELD):
		return []
	seeded: list[str] = []
	for spec in HAZMAT_PROFILES:
		name = spec["profile_name"]
		if not frappe.db.exists("Item", spec["item"]):
			continue
		if not frappe.db.exists("Hazmat Profile", name):
			doc = frappe.get_doc(
				{
					"doctype": "Hazmat Profile",
					"profile_name": name,
					"un_number": spec["un_number"],
					"proper_shipping_name": spec["proper_shipping_name"],
					"storage_class": spec["storage_class"],
					"water_hazard_class": spec["water_hazard_class"],
					"signal_word": spec["signal_word"],
					"sds_reference": spec["sds_reference"],
					"sds_version": spec["sds_version"],
					"sds_revision_date": spec["sds_revision_date"],
					"pictograms": [{"pictogram": code} for code in spec["pictograms"]],
					"statements": [
						{"statement_type": kind, "code": code, "statement_text": text}
						for kind, code, text in spec["statements"]
					],
				}
			)
			doc.insert(ignore_permissions=True)
		frappe.db.set_value(
			"Item",
			spec["item"],
			{ITEM_PROFILE_FIELD: name, ITEM_MANDATORY_FIELD: spec["mandatory"]},
			update_modified=False,
		)
		seeded.append(name)
	# The batches exist by now, so their derived UN-number/Lagerklasse mirrors are refreshed
	# from the freshly linked profiles (URS-W2-024).
	from rheinwerk_mes.setup.w2_hazmat import backfill_batch_mirrors

	backfill_batch_mirrors()
	return seeded


def seed_quarantine_location() -> str | None:
	"""Quarantine storage location NORD-Q-01 (URS-W2-012 AC-1)."""
	if not _has_field("Storage Location", "is_quarantine_location"):
		return None
	warehouse = f"{QUARANTINE_LOCATION['warehouse']} - {COMPANY_ABBR}"
	if not frappe.db.exists("Warehouse", warehouse):
		return None
	name = QUARANTINE_LOCATION["storage_location_name"]
	if not frappe.db.exists("Storage Location", name):
		frappe.get_doc(
			{
				"doctype": "Storage Location",
				"storage_location_name": name,
				"warehouse": warehouse,
				"is_group": 0,
				"company": COMPANY,
				"is_quarantine_location": 1,
			}
		).insert(ignore_permissions=True)
	elif not frappe.db.get_value("Storage Location", name, "is_quarantine_location"):
		frappe.db.set_value("Storage Location", name, "is_quarantine_location", 1)
	return name


def seed_third_production_order(bom_no: str) -> str | None:
	"""Work order PO-2026-0003 — the second consumer of BATCH-A-0002 (URS-W2-002 AC-2)."""
	name = "PO-2026-0003"
	if frappe.db.exists("Work Order", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Work Order",
			"naming_series": WORK_ORDER_SERIES,
			"company": COMPANY,
			"production_item": SECOND_PRODUCTION_ORDER["production_item"],
			"bom_no": bom_no,
			"qty": 10.0,
			"stock_uom": frappe.db.get_value("Item", SECOND_PRODUCTION_ORDER["production_item"], "stock_uom"),
			"wip_warehouse": f"{SECOND_PRODUCTION_ORDER['wip_warehouse']} - {COMPANY_ABBR}",
			"fg_warehouse": f"{SECOND_PRODUCTION_ORDER['fg_warehouse']} - {COMPANY_ABBR}",
			"planned_start_date": SECOND_PRODUCTION_ORDER["planned_start_date"],
			"planned_end_date": SECOND_PRODUCTION_ORDER["planned_end_date"],
		}
	)
	if _has_field("Work Order", "production_line"):
		doc.production_line = SECOND_PRODUCTION_ORDER["production_line"]
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_qa_states() -> dict[str, str]:
	"""Put the raw-material fixtures into `Released` (TC-W2-009 preconditions)."""
	if not _has_field("Batch", "qa_state"):
		return {}
	from rheinwerk_mes.genealogy.qa_state import QUARANTINED, RELEASED, transition

	states: dict[str, str] = {}
	for batch in RELEASED_BATCHES:
		if not frappe.db.exists("Batch", batch):
			continue
		if frappe.db.get_value("Batch", batch, "qa_state") == QUARANTINED:
			transition(batch, RELEASED, reason="Eingangsprüfung bestanden (Fixture)")
		states[batch] = frappe.db.get_value("Batch", batch, "qa_state")
	return states


def _posted_chain_entry(work_order: str) -> bool:
	return bool(frappe.db.exists("Stock Entry", {"work_order": work_order, "docstatus": 1}))


#: The chain is stock-neutral: what it will consume is pre-stocked *before* its first
#: posting, what it produces is issued again afterwards. Both dates sit inside the fixture
#: shelf lives, and the pre-stock date is early enough that no backdated test posting ever
#: sees a negative batch balance.
CHAIN_PRESTOCK_DATE = "2026-03-01"
CHAIN_REBALANCE_DATE = "2026-04-16"


def _chain_movements() -> tuple[dict[tuple[str, str, str], float], dict[tuple[str, str, str], float]]:
	"""Consumed and produced quantities of the chain, keyed by (item, batch, warehouse)."""
	consumed: dict[tuple[str, str, str], float] = {}
	produced: dict[tuple[str, str, str], float] = {}
	for step in GENEALOGY_CHAIN:
		for item, batch, qty, warehouse in step["consume"]:
			key = (item, batch, f"{warehouse} - {COMPANY_ABBR}")
			consumed[key] = consumed.get(key, 0.0) + qty
		item, batch, qty, warehouse = step["produce"]
		key = (item, batch, f"{warehouse} - {COMPANY_ABBR}")
		produced[key] = produced.get(key, 0.0) + qty
	return consumed, produced


def _balancing_entry(stock_entry_type: str, posting_date: str, rows: list[dict]) -> None:
	if not rows:
		return
	doc = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": stock_entry_type,
			"company": COMPANY,
			"set_posting_time": 1,
			"posting_date": posting_date,
			"posting_time": "06:00:00",
			"items": rows,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()


def _balancing_row(key: tuple[str, str, str], qty: float, inbound: bool) -> dict:
	item, batch, warehouse = key
	row = {
		"item_code": item,
		"qty": qty,
		"uom": frappe.db.get_value("Item", item, "stock_uom"),
		"use_serial_batch_fields": 1,
		"batch_no": batch,
	}
	row.update({"t_warehouse": warehouse, "basic_rate": 5.0} if inbound else {"s_warehouse": warehouse})
	return row


def prestock_for_chain() -> None:
	"""Pre-stock what the genealogy chain consumes, so it shifts no W1 warehouse fixture.

	The supplier lot is excluded: it is received by `seed_supplier_batch` and consumed in
	full, which is exactly the stock-neutral behaviour wanted.
	"""
	consumed, _produced = _chain_movements()
	rows = [
		_balancing_row(key, qty, inbound=True)
		for key, qty in consumed.items()
		if key[1] != SUPPLIER_BATCH["batch_id"]
	]
	_balancing_entry("Material Receipt", CHAIN_PRESTOCK_DATE, rows)


def _rebalance_after_chain() -> None:
	"""Issue what the chain produced, restoring the pre-chain quantities."""
	_consumed, produced = _chain_movements()
	rows = [
		_balancing_row(key, qty, inbound=False)
		for key, qty in produced.items()
		if key[1] != SUPPLIER_BATCH["batch_id"]
	]
	_balancing_entry("Material Issue", CHAIN_REBALANCE_DATE, rows)


def seed_genealogy_fixture(orders: dict[str, str]) -> list[str]:
	"""Post the genealogy chain: SUP-K7-0001 → BATCH-A-0002 → BATCH-C-1001/1002.

	The links are written by the `Stock Entry` hooks, not by this seeder, so the fixture
	exercises the same write path production uses (URS-W2-001).
	"""
	if not _has_field("Batch", "genealogy_links"):
		return []
	pending = [
		step
		for step in GENEALOGY_CHAIN
		if orders.get(step["order"]) and not _posted_chain_entry(orders[step["order"]])
	]
	if pending:
		prestock_for_chain()
	posted = False
	produced: list[str] = []
	for step in GENEALOGY_CHAIN:
		work_order = orders.get(step["order"])
		if not work_order or _posted_chain_entry(work_order):
			produced.append(step["produce"][1])
			continue
		issue_rows = [
			{
				"item_code": item,
				"qty": qty,
				"s_warehouse": f"{warehouse} - {COMPANY_ABBR}",
				"uom": frappe.db.get_value("Item", item, "stock_uom"),
				"use_serial_batch_fields": 1,
				"batch_no": batch,
			}
			for item, batch, qty, warehouse in step["consume"]
		]
		item, batch, qty, warehouse = step["produce"]
		receipt_row = {
			"item_code": item,
			"qty": qty,
			"t_warehouse": f"{warehouse} - {COMPANY_ABBR}",
			"uom": frappe.db.get_value("Item", item, "stock_uom"),
			"basic_rate": 5.0,
			"use_serial_batch_fields": 1,
			"batch_no": batch,
		}
		for stock_entry_type, rows in (
			("Material Issue", issue_rows),
			("Material Receipt", [receipt_row]),
		):
			doc = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": stock_entry_type,
					"company": COMPANY,
					"work_order": work_order,
					"set_posting_time": 1,
					"posting_date": step["posting_date"],
					"posting_time": "08:00:00",
					"items": rows,
				}
			)
			doc.insert(ignore_permissions=True)
			doc.submit()
		posted = True
		produced.append(batch)
	if posted:
		_rebalance_after_chain()
	return produced


# --------------------------------------------------------------------------------------
# W2-4/W2-5 quality fixture (TST-W2-traceability-quality §1)
# --------------------------------------------------------------------------------------

#: Inspection template of the compound with its three parameters and limits
#: (URS-W2-013 AC-1). Units are carried on the parameter master (`rw_unit`) and rendered
#: suffixed inside the reading inputs (URS-W2-015 AC-2).
INSPECTION_TEMPLATE = "QIT-COMPOUND"

INSPECTION_PARAMETERS = (
	{"specification": "Viskosität", "unit": "mPa·s", "min_value": 1200.0, "max_value": 1400.0},
	{"specification": "Dichte", "unit": "g/cm³", "min_value": 1.02, "max_value": 1.06},
	{"specification": "Feuchte", "unit": "%", "min_value": 0.0, "max_value": 0.5},
)


def seed_inspection_template() -> str | None:
	"""Template QIT-COMPOUND on RW-CHM-0003 (URS-W2-013 AC-1, TC-W2-018)."""
	if not frappe.db.exists("DocType", "Quality Inspection Template"):
		return None
	has_unit = _has_field("Quality Inspection Parameter", "rw_unit")
	for spec in INSPECTION_PARAMETERS:
		if not frappe.db.exists("Quality Inspection Parameter", spec["specification"]):
			frappe.get_doc(
				{
					"doctype": "Quality Inspection Parameter",
					"parameter": spec["specification"],
				}
			).insert(ignore_permissions=True)
		if has_unit:
			frappe.db.set_value(
				"Quality Inspection Parameter", spec["specification"], "rw_unit", spec["unit"]
			)
	if not frappe.db.exists("Quality Inspection Template", INSPECTION_TEMPLATE):
		doc = frappe.get_doc(
			{
				"doctype": "Quality Inspection Template",
				"quality_inspection_template_name": INSPECTION_TEMPLATE,
			}
		)
		for spec in INSPECTION_PARAMETERS:
			doc.append(
				"item_quality_inspection_parameter",
				{
					"specification": spec["specification"],
					"numeric": 1,
					"min_value": spec["min_value"],
					"max_value": spec["max_value"],
				},
			)
		doc.insert(ignore_permissions=True)
	if not frappe.db.get_value("Item", "RW-CHM-0003", "quality_inspection_template"):
		frappe.db.set_value("Item", "RW-CHM-0003", "quality_inspection_template", INSPECTION_TEMPLATE)
	return INSPECTION_TEMPLATE


# W2-8: a pallet (Handling Unit) for the pallet-balance / repacking journeys (URS-W2-025/027).
# The pallet is a *reference* over the ledger — its content mirrors the BATCH-A-0001 opening
# balance and is never a second quantity store. A second, empty pallet gives a repack target.
PALLETS = (
	{
		"barcode": "HU-000123",
		"hu_type": "Palette",
		"warehouse": "RM Lager Nord",
		"storage_location": "NORD-A-01-01",
		"contents": (("RW-CHM-0001", "BATCH-A-0001", 500.0),),
	},
	{
		"barcode": "HU-000124",
		"hu_type": "Palette",
		"warehouse": "RM Lager Nord",
		"storage_location": "NORD-A-01-01",
		"contents": (),
	},
)


def seed_pallets() -> list[str]:
	"""Handling-Unit pallets for the W2-8 warehouse journeys; safe to re-run (URS-W2-025)."""
	if not frappe.db.exists("DocType", "Handling Unit"):
		return []
	seeded = []
	for spec in PALLETS:
		warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
		if not frappe.db.exists("Warehouse", warehouse):
			continue
		existing = frappe.db.get_value("Handling Unit", {"barcode": spec["barcode"]})
		if existing:
			seeded.append(existing)
			continue
		unit = frappe.get_doc(
			{
				"doctype": "Handling Unit",
				"barcode": spec["barcode"],
				"hu_type": spec["hu_type"],
				"warehouse": warehouse,
				"storage_location": spec["storage_location"],
				"company": COMPANY,
				"contents": [
					{"item": item, "batch_no": batch, "qty": qty, "uom": "Kg"}
					for item, batch, qty in spec["contents"]
				],
			}
		)
		unit.insert(ignore_permissions=True)
		seeded.append(unit.name)
	return seeded


# --------------------------------------------------------------------------------------
# W3-6: ADR transport data and the two dispatch fixtures (URS-W3-018)
# --------------------------------------------------------------------------------------

#: ADR transport data completing the W2-7 profiles (URS-W3-018 AC-1). UN 1263 "FARBE" is the
#: ADR entry the URS names for RW-CHM-0003; UN 1866 "HARZLÖSUNG" is its counterpart for the
#: base resin. Proper shipping names are carried as ADR 3.1.2 spells them (upper case on
#: documents); both are class 3, packing group III, tunnel restriction code D/E.
ADR_TRANSPORT_DATA = (
	{
		"profile": "HAZ-RW-CHM-0001",
		"proper_shipping_name": "HARZLÖSUNG",
		"adr_class": "3",
		"adr_packing_group": "III",
		"adr_tunnel_code": "D/E",
		"adr_label_numbers": "3",
	},
	{
		"profile": "HAZ-RW-CHM-0003",
		"proper_shipping_name": "FARBE",
		"adr_class": "3",
		"adr_packing_group": "III",
		"adr_tunnel_code": "D/E",
		"adr_label_numbers": "3",
	},
)

#: The AC-2 counter-fixture: a hazmat item whose profile carries the storage-class and SDS
#: data but **no UN number and no ADR classification**, so dispatching its batch is refused
#: (URS-W3-018 AC-2, TC-W3-022). Such a profile cannot be *created* through the form — the
#: W2-7 controller requires the UN number — but it is exactly what a migrated or
#: half-maintained record looks like, so the fixture writes the gap at database level.
INCOMPLETE_ADR_ITEM = {
	"item_code": "RW-CHM-0004",
	"item_name": "Rheinol Reiniger R2",
	"item_group": "Products",
	"stock_uom": "Kg",
	"profile_name": "HAZ-RW-CHM-0004",
	"storage_class": "3",
	"water_hazard_class": "2",
	"signal_word": "Gefahr",
	"sds_reference": "SDS-RW-0004",
	"sds_version": "0.9",
	"sds_revision_date": "2026-03-05",
	"batch_id": "BATCH-D-0001",
	"expiry_date": "2027-09-30",
	"manufacturing_date": "2026-03-05",
	"warehouse": "FG Lager Süd",
	"qty": 60.0,
}

#: A dispatch handling unit at the finished-goods warehouse, so the dispatch station's
#: scanner path has something to scan (URS-W3-018 design conformance, URS-W3-020 AC-2). Like
#: every W2-8 handling unit it is a *reference* over the ledger, never a second quantity store.
DISPATCH_PALLET = {
	"barcode": "HU-000125",
	"hu_type": "Palette",
	"warehouse": "FG Lager Süd",
	"contents": (("RW-CHM-0003", "BATCH-C-1001", 200.0),),
}


def seed_adr_transport_data() -> list[str]:
	"""W3-6: complete the hazmat profiles with their ADR transport data (URS-W3-018 AC-1)."""
	if not frappe.db.exists("DocType", "Hazmat Profile") or not _has_field("Hazmat Profile", "adr_class"):
		return []
	seeded: list[str] = []
	for spec in ADR_TRANSPORT_DATA:
		if not frappe.db.exists("Hazmat Profile", spec["profile"]):
			continue
		doc = frappe.get_doc("Hazmat Profile", spec["profile"])
		values = {key: value for key, value in spec.items() if key != "profile"}
		if all(doc.get(key) == value for key, value in values.items()):
			seeded.append(doc.name)
			continue
		doc.update(values)
		doc.save(ignore_permissions=True)
		seeded.append(doc.name)
	return seeded


def seed_incomplete_adr_item() -> str | None:
	"""W3-6: the hazmat item whose profile lacks its UN number (URS-W3-018 AC-2)."""
	if not frappe.db.exists("DocType", "Hazmat Profile"):
		return None
	from rheinwerk_mes.regulatory_hazmat.profiles import ITEM_MANDATORY_FIELD, ITEM_PROFILE_FIELD

	if not _has_field("Item", ITEM_PROFILE_FIELD):
		return None
	spec = INCOMPLETE_ADR_ITEM
	warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
	if not frappe.db.exists("Warehouse", warehouse):
		return None
	if not frappe.db.exists("Item", spec["item_code"]):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": spec["item_code"],
				"item_name": spec["item_name"],
				"item_group": spec["item_group"],
				"stock_uom": spec["stock_uom"],
				"has_batch_no": 1,
				"has_expiry_date": 1,
				"shelf_life_in_days": 540,
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Hazmat Profile", spec["profile_name"]):
		# Inserted with a placeholder UN number (the controller requires one) and then
		# emptied at database level: the fixture is the *gap*, not a way around the rule.
		frappe.get_doc(
			{
				"doctype": "Hazmat Profile",
				"profile_name": spec["profile_name"],
				"un_number": "UN 1993",
				"storage_class": spec["storage_class"],
				"water_hazard_class": spec["water_hazard_class"],
				"signal_word": spec["signal_word"],
				"sds_reference": spec["sds_reference"],
				"sds_version": spec["sds_version"],
				"sds_revision_date": spec["sds_revision_date"],
			}
		).insert(ignore_permissions=True)
	frappe.db.set_value(
		"Hazmat Profile",
		spec["profile_name"],
		{"un_number": None, "adr_dispatch_ready": 0},
		update_modified=False,
	)
	frappe.db.set_value(
		"Item",
		spec["item_code"],
		{ITEM_PROFILE_FIELD: spec["profile_name"], ITEM_MANDATORY_FIELD: 1},
		update_modified=False,
	)
	if not frappe.db.exists("Batch", spec["batch_id"]):
		frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": spec["batch_id"],
				"item": spec["item_code"],
				"expiry_date": spec["expiry_date"],
				"manufacturing_date": spec["manufacturing_date"],
				"qty_original": spec["qty"],
			}
		).insert(ignore_permissions=True)
	if _never_received(spec["batch_id"]):
		receipt = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": COMPANY,
				"set_posting_time": 1,
				"posting_date": spec["manufacturing_date"],
				"posting_time": "06:00:00",
				"items": [
					{
						"item_code": spec["item_code"],
						"qty": spec["qty"],
						"t_warehouse": warehouse,
						"uom": spec["stock_uom"],
						"basic_rate": 4.0,
						"use_serial_batch_fields": 1,
						"batch_no": spec["batch_id"],
					}
				],
			}
		)
		receipt.insert(ignore_permissions=True)
		receipt.submit()
	return spec["item_code"]


def seed_dispatch_pallet() -> str | None:
	"""W3-6: the finished-goods handling unit the dispatch station scans (URS-W3-018)."""
	if not frappe.db.exists("DocType", "Handling Unit"):
		return None
	spec = DISPATCH_PALLET
	warehouse = f"{spec['warehouse']} - {COMPANY_ABBR}"
	if not frappe.db.exists("Warehouse", warehouse):
		return None
	existing = frappe.db.get_value("Handling Unit", {"barcode": spec["barcode"]})
	if existing:
		return existing
	unit = frappe.get_doc(
		{
			"doctype": "Handling Unit",
			"barcode": spec["barcode"],
			"hu_type": spec["hu_type"],
			"warehouse": warehouse,
			"company": COMPANY,
			"contents": [
				{"item": item, "batch_no": batch, "qty": qty, "uom": "Kg"}
				for item, batch, qty in spec["contents"]
			],
		}
	)
	unit.insert(ignore_permissions=True)
	return unit.name


def seed_all() -> dict:
	"""Seed every programme fixture; safe to re-run."""
	summary = {
		"company": seed_company(),
	}
	seed_uoms()
	seed_item_groups()
	summary["items"] = seed_items()
	summary["warehouses"] = seed_warehouses()
	seed_warehouse_reservation_flags()
	summary["storage_locations"] = seed_storage_locations()
	summary["batches"] = seed_batches()
	summary["divisions"] = seed_divisions()
	summary["production_lines"] = seed_production_lines()
	summary["work_centres"] = seed_work_centres()
	seed_workstation_limits()
	summary["operations"] = seed_operations()
	# W3-2: TJ/TPZ norms, LINE-1 changeover norms and the work-centre capacity ceilings
	# (URS-W3-006/007/008) — after the operations and work centres they reference.
	summary["time_norms"] = seed_time_norms()
	summary["changeover_norms"] = seed_changeover_norms()
	seed_work_centre_capacity()
	summary["routing"] = seed_routing()
	summary["bom"] = seed_bom()
	summary["recipe_governance"] = seed_recipe_governance(summary["bom"])
	summary["isa88_recipe"] = seed_isa88_recipe(summary["bom"])
	summary["production_order"] = seed_production_order(summary["bom"])
	summary["second_production_order"] = seed_second_production_order(summary["bom"])
	# W2-1/2/3: canonical-batch dispositions, quarantine place and the genealogy chain.
	summary["supplier_batch"] = seed_supplier_batch()
	summary["quarantine_location"] = seed_quarantine_location()
	summary["third_production_order"] = seed_third_production_order(summary["bom"])
	summary["qa_states"] = seed_qa_states()
	summary["genealogy"] = seed_genealogy_fixture(
		{
			"first": summary["production_order"],
			"second": summary["second_production_order"],
			"third": summary["third_production_order"],
		}
	)
	# W2-4/W2-5: the inspection template the quality gates and the CoA work from.
	summary["inspection_template"] = seed_inspection_template()
	# W2-7: hazmat master data on the item masters and their batches (URS-W2-023/024).
	summary["hazmat_profiles"] = seed_hazmat_profiles()
	# W3-6: ADR transport data at the shipping boundary plus its two dispatch fixtures
	# (URS-W3-018).
	summary["adr_transport_data"] = seed_adr_transport_data()
	summary["incomplete_adr_item"] = seed_incomplete_adr_item()
	summary["legacy_refs"] = seed_legacy_refs()
	summary["pallets"] = seed_pallets()
	summary["dispatch_pallet"] = seed_dispatch_pallet()
	summary["personas"] = seed_personas()
	# W1-8: the personas only exist now, so their transition roles are granted here as well
	# as from the installer (URS-W1-029).
	summary["persona_roles"] = assign_persona_roles()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
