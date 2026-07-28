"""W0 canonical Work Centre on the anchor `Workstation`.

TC-W0-006 (URS-W0-005) — `production_line` / `division` extensions and the OFBiz
asset-ledger separation (CDM-08, ADR-010).
"""

from __future__ import annotations

LINE = "LINE-1"
WORK_CENTRES = ("MIX-01", "FILL-01")


def test_tc_w0_006_work_centres_filter_by_production_line(site):
	"""TC-W0-006 step 1 (URS-W0-005 AC-1): both LINE-1 work centres exist on the anchor
	`Workstation` and a filter on `production_line` returns exactly these two."""
	on_line = set(site.get_all("Workstation", filters={"production_line": LINE}, pluck="name"))
	assert on_line == set(WORK_CENTRES)
	for name in WORK_CENTRES:
		workstation = site.get_doc("Workstation", name)
		assert workstation.production_line == LINE
		assert site.db.exists("Division", workstation.division)


def test_tc_w0_006_extensions_are_custom_fields_on_the_anchor(site):
	"""TC-W0-006 (URS-W0-005): the CDM-08 extensions are `rheinwerk_mes` Custom Fields —
	the `Workstation` schema itself is untouched."""
	for fieldname in ("production_line", "division"):
		assert site.db.exists(
			"Custom Field",
			{"dt": "Workstation", "fieldname": fieldname, "module": "Manufacturing Core"},
		)
		assert not site.db.exists("DocField", {"parent": "Workstation", "fieldname": fieldname})


def test_tc_w0_006_no_asset_ledger_record_in_the_mes(site):
	"""TC-W0-006 step 2 (URS-W0-005 AC-2): a machine imported from an OFBiz FixedAsset
	group becomes a Workstation only — the MES creates no asset-accounting record
	(asset ledger stays with the group ERP, ADR-002)."""
	assert not site.get_all("Asset", filters={"asset_name": ("in", WORK_CENTRES)}, pluck="name")
	assert not site.get_all("Asset", filters={"item_code": ("in", WORK_CENTRES)}, pluck="name")
	workstation_fields = {
		row.fieldname
		for row in site.get_meta("Workstation").fields
		if row.fieldtype == "Link" and row.options in ("Asset", "Asset Category", "Cost Center")
	}
	assert not workstation_fields


def test_tc_w0_006_division_is_a_plant_area_tree(site):
	"""TC-W0-006 (URS-W0-005): `division` resolves against the plant-area tree seeded
	from the Qcadoo division hierarchy."""
	assert site.get_meta("Division").is_tree
	assert site.db.get_value("Division", "Mischerei", "parent_division") == "Werk Nord"
	assert site.db.get_value("Division", "Werk Nord", "is_group") == 1
