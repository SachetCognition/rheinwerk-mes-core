"""Programme fixture seeding for the canonical Work Centre (idempotent).

Seeds the shared work-centre fixtures named in `docs/test/TST-W0-foundation.md` §1 so the
site-backed acceptance suite (TC-W0-006) and the local demo stack start from the same data:

* company "Rheinwerk Chemie GmbH" (abbr RWC), German locale defaults
* plant-area divisions (Werk Nord ▸ Mischerei / Abfüllung) as a nested-set tree
* production line LINE-1
* work centres LINE-1/MIX-01 and LINE-1/FILL-01 on the anchor `Workstation`
* `legacy_refs` source identifiers for the two work centres (OFBiz FixedAsset)

Run with::

    bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all
"""

from __future__ import annotations

import frappe

COMPANY = "Rheinwerk Chemie GmbH"
COMPANY_ABBR = "RWC"

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

# Source-system identifiers preserved out of the primary key (URS-W0-003, URS-W0-014):
# both work centres migrate from OFBiz FixedAsset machine groups (CDM-08, ADR-010).
LEGACY_REFS = (
	{
		"name": "MIX-01",
		"refs": ({"source_system": "OFBiz", "source_entity": "FixedAsset", "source_identifier": "MIXER-01"},),
	},
	{
		"name": "FILL-01",
		"refs": (
			{"source_system": "OFBiz", "source_entity": "FixedAsset", "source_identifier": "FILLER-01"},
		),
	},
)


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).get_field(fieldname))


def _backfill(doctype: str, name: str, values: dict[str, str]) -> None:
	"""Fill still-empty extension fields on a record seeded before they existed."""
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
	"""Run the ERPNext setup wizard once, so substrate defaults exist before seeding."""
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


def seed_divisions() -> list[str]:
	"""Plant-area tree backing the Work Centre `division` link (CDM-08)."""
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
	"""Work centres on the anchor `Workstation`, extended with production_line / division."""
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


def seed_legacy_refs() -> list[str]:
	"""Attach the OFBiz FixedAsset source identifiers to the seeded work centres."""
	seeded = []
	for spec in LEGACY_REFS:
		if not _has_field("Workstation", "legacy_refs") or not frappe.db.exists("Workstation", spec["name"]):
			continue
		doc = frappe.get_doc("Workstation", spec["name"])
		known = {row.source_identifier for row in doc.get("legacy_refs") or []}
		missing = [ref for ref in spec["refs"] if ref["source_identifier"] not in known]
		if missing:
			for ref in missing:
				doc.append("legacy_refs", ref)
			doc.save(ignore_permissions=True)
		seeded.append(spec["name"])
	return seeded


def seed_all() -> dict:
	"""Seed every Work Centre fixture; safe to re-run."""
	summary = {"company": seed_company()}
	summary["divisions"] = seed_divisions()
	summary["production_lines"] = seed_production_lines()
	summary["work_centres"] = seed_work_centres()
	summary["legacy_refs"] = seed_legacy_refs()
	frappe.db.commit()
	print(frappe.as_json(summary))
	return summary
