"""Programme fixture seeding (idempotent).

Seeds the canonical item master named in `docs/test/TST-W0-foundation.md` §1 so
that the acceptance suite and the local demo stack start from the same data:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* UoMs kg / sack / pail with the item-level pack conversions
* items RW-CHM-0001 … RW-CHM-0003
* `legacy_refs` source-system identifiers for the migrated items

Run with::

    bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all

Later waves extend this module (never replace it) as their canonical entities
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
		"shelf_life_in_days": 365,
	},
	{
		"item_code": "RW-CHM-0002",
		"item_name": "Additiv K7",
		"item_group": "Raw Material",
		"stock_uom": "Kg",
		"pack_uom": "Pail",
		"pack_factor": 5.0,
		"shelf_life_in_days": 180,
	},
	{
		"item_code": "RW-CHM-0003",
		"item_name": "Rheinol 40 Compound",
		"item_group": "Products",
		"stock_uom": "Kg",
		"pack_uom": None,
		"pack_factor": None,
		"shelf_life_in_days": 540,
	},
)

# Source-system identifiers preserved out of the primary key (URS-W0-003 AC-2).
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
)


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).get_field(fieldname))


def _complete_setup_wizard() -> None:
	"""Run the ERPNext setup wizard once, so substrate defaults (item groups,
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
	"""Canonical item master on the anchor `Item` DocType (URS-W0-003 AC-1)."""
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
				"has_batch_no": 1,
				"has_expiry_date": 1,
				"shelf_life_in_days": spec["shelf_life_in_days"],
				"create_new_batch": 1,
			}
		)
		if spec["pack_uom"]:
			doc.append("uoms", {"uom": spec["pack_uom"], "conversion_factor": spec["pack_factor"]})
		doc.insert(ignore_permissions=True)
		seeded.append(doc.name)
	return seeded


def seed_legacy_refs() -> list[str]:
	"""Attach the source-system identifiers of the migrated items (URS-W0-003 AC-2)."""
	seeded = []
	for spec in LEGACY_REFS:
		if not _has_field(spec["doctype"], "legacy_refs"):
			continue
		if not frappe.db.exists(spec["doctype"], spec["name"]):
			continue
		doc = frappe.get_doc(spec["doctype"], spec["name"])
		known = {row.source_identifier for row in doc.get("legacy_refs") or []}
		missing = [ref for ref in spec["refs"] if ref["source_identifier"] not in known]
		if missing:
			for ref in missing:
				doc.append("legacy_refs", ref)
			doc.save(ignore_permissions=True)
		seeded.append(spec["name"])
	return seeded


def seed_all() -> dict:
	"""Seed every programme fixture; safe to re-run."""
	summary = {"company": seed_company()}
	seed_uoms()
	seed_item_groups()
	summary["items"] = seed_items()
	summary["legacy_refs"] = seed_legacy_refs()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
