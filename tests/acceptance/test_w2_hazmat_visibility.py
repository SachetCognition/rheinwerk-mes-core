"""W2-7 — hazmat visibility in warehouse and trace surfaces (URS-W2-024).

TC-W2-032 (design conformance): with BATCH-A-0001 carrying the URS-W2-023 profile, the RM
Lager Nord stock view and the Trace Ribbon both render Lagerklasse 3 and UN 1866 as data —
columns in the stock view, a chip on every ribbon node — and never behind progressive
disclosure (design skill: nothing hides on desktop; status = icon + label + colour).
"""

from __future__ import annotations

import pytest

frappe = pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.contracts")
profiles = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.profiles")
views = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.views")

WAREHOUSE = "RM Lager Nord - RWC"
BATCH = "BATCH-A-0001"
FG_BATCH = "BATCH-C-1001"


def _require_fixture(site) -> None:
	if not site.db.exists("Hazmat Profile", "HAZ-RW-CHM-0001") or not site.db.exists("Batch", BATCH):
		pytest.skip("hazmat fixture not seeded on this site")


def test_hazmat_chip_is_never_colour_only(site):
	"""URS-W2-024 design conformance: the chip always carries label + icon + colour, and the
	acute Lagerklassen of TRGS 510 use the red signal token."""
	chip = contracts.hazmat_chip({"name": "HAZ-X", "un_number": "UN 1866", "storage_class": "3"})
	assert chip["label"] == "UN 1866 · Lagerklasse 3 — Entzündbare Flüssigkeiten"
	assert chip["icon"] and chip["token"] == "--rw-signal-red"
	# Chronically toxic / corrosive classes are advisory amber, storage class 12 informational.
	assert contracts.signal_for_storage_class("8A")["token"] == "--rw-signal-amber"
	assert contracts.signal_for_storage_class("12")["token"] == "--rw-signal-blue"
	# Non-hazardous material has no chip at all — never an empty placeholder.
	assert contracts.hazmat_chip(None) is None


def test_tc_w2_032_stock_view_carries_hazmat_columns(site):
	"""TC-W2-032 (URS-W2-024 AC-1): the RM Lager Nord stock view lists Lagerklasse and UN
	number as columns on the hazmat batch, and leaves them empty for non-hazardous stock."""
	_require_fixture(site)
	rows = {row["batch"]: row for row in views.stock_view(WAREHOUSE)}

	assert BATCH in rows, sorted(rows)
	row = rows[BATCH]
	assert row["hazmat_un_number"] == "UN 1866"
	assert row["hazmat_storage_class"] == "3"
	assert row["hazmat_storage_class_label"] == "Lagerklasse 3 — Entzündbare Flüssigkeiten"
	assert row["hazmat"]["tone"] == "red"
	# Dates German-first, mass in kg (design skill i18n rules).
	assert row["expiry_date"] == "31.12.2026"
	assert row["uom"] == "Kg"

	non_hazardous = [row for row in rows.values() if row["item"] == "RW-CHM-0002"]
	assert non_hazardous and all(row["hazmat"] is None for row in non_hazardous)


def test_tc_w2_032_trace_ribbon_nodes_carry_the_hazmat_chip(site):
	"""TC-W2-032 (URS-W2-024 AC-1): every ribbon node of a hazmat batch carries the chip, in
	addition to — never instead of — its `qa_state` pill, and the node/state set is unchanged
	from the W2-1 ribbon model."""
	_require_fixture(site)
	from rheinwerk_mes.genealogy import ribbon as genealogy_ribbon

	plain = genealogy_ribbon.ribbon(FG_BATCH)
	model = views.ribbon(FG_BATCH)

	assert [node["batch"] for node in model["left"]] == [node["batch"] for node in plain["left"]]
	assert model["focus"]["hazmat_un_number"] == "UN 1263"

	upstream = {node["batch"]: node for node in model["left"]}
	hazmat_node = upstream[BATCH] if BATCH in upstream else None
	if hazmat_node is None:
		pytest.skip("genealogy fixture does not link BATCH-A-0001 upstream of BATCH-C-1001")
	assert hazmat_node["hazmat_storage_class"] == "3"
	pill_states = [pill["state"] for pill in hazmat_node["pills"]]
	assert "hazmat" in pill_states
	assert hazmat_node["qa_state"] in pill_states


def test_tc_w2_032_hazmat_fields_are_not_behind_progressive_disclosure(site):
	"""TC-W2-032 (URS-W2-024 AC-1): the hazmat fields render in list views and their section is
	neither collapsible nor conditionally hidden — nothing hides on desktop."""
	_require_fixture(site)
	for fieldname in (profiles.BATCH_UN_NUMBER_FIELD, profiles.BATCH_STORAGE_CLASS_FIELD):
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Batch", "fieldname": fieldname},
			["in_list_view", "in_standard_filter", "depends_on", "hidden"],
			as_dict=True,
		)
		assert field, fieldname
		assert field.in_list_view and field.in_standard_filter
		assert not field.depends_on
		assert not field.hidden

	section = frappe.db.get_value(
		"Custom Field",
		{"dt": "Item", "fieldname": "rw_hazmat_section"},
		["collapsible", "hidden", "depends_on"],
		as_dict=True,
	)
	assert section and not section.collapsible and not section.hidden and not section.depends_on
