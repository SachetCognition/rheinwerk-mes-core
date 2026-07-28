"""W3-6 — hazmat dispatch label data (URS-W3-018 AC-1).

TC-W3-021: at the dispatch station W. Braun scans the handling unit or the batch and the
label data of BATCH-C-1001 out of `FG Lager Süd - RWC` carries UN 1263, "FARBE", ADR class 3,
packing group III, the batch id and the net quantity in kg.

White space in all three legacy systems (dossier §6.3) — there is no parity contract; the
rules asserted here come from the URS, from ADR 5.4.1.1.1 (order and upper-case shipping
name) and from the design skill (German-first, kg, DD.MM.YYYY). See
`docs/design/W3-hazmat-dispatch.md`.
"""

from __future__ import annotations

import re

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.contracts")
dispatch = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.dispatch")
labels = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.labels")

ITEM = "RW-CHM-0003"
BATCH = "BATCH-C-1001"
PROFILE = "HAZ-RW-CHM-0003"
WAREHOUSE = "FG Lager Süd - RWC"
SCANNED_UNIT = "HU-000123"


def _require_fixture(site) -> None:
	if not site.db.exists("Hazmat Profile", PROFILE) or not site.db.exists("Batch", BATCH):
		pytest.skip("W3 hazmat dispatch fixture not seeded on this site")


def test_tc_w3_021_label_data_is_exact(site):
	"""TC-W3-021 (URS-W3-018 AC-1): the label of BATCH-C-1001 carries UN 1263, "FARBE",
	class 3, PG III, the batch id and the net quantity in kg."""
	_require_fixture(site)

	label = labels.label_model(BATCH, warehouse=WAREHOUSE)

	assert label["batch"] == BATCH
	assert label["item"] == ITEM
	assert label["warehouse"] == WAREHOUSE
	assert label["un_number"] == "UN 1263"
	assert label["proper_shipping_name"] == "FARBE"
	assert label["adr_class"] == "3"
	assert label["packing_group"] == "III"
	# Net quantity is the ledger balance in the dispatch warehouse, in kg with the German
	# decimal separator — never a stored second quantity.
	from rheinwerk_mes.warehouse.availability import ledger_balance

	assert label["net_qty"] == pytest.approx(float(ledger_balance(ITEM, WAREHOUSE, BATCH, True)))
	assert label["net_qty_display"] == f"{label['net_qty']:.3f}".replace(".", ",") + " kg"
	assert label["net_qty"] > 0
	assert label["complete"] is True
	assert label["missing"] == []


def test_tc_w3_021_label_is_german_first_and_ordered_as_adr_requires(site):
	"""TC-W3-021 (URS-W3-018 AC-1): no bare codes, ADR 5.4.1.1.1 order, DD.MM.YYYY.

	The transport document line is the sequence ADR 5.4.1.1.1 prescribes — UN number,
	proper shipping name in upper case, class, packing group, tunnel restriction code — and
	class/packing group are also rendered with their German designation, so a clerk never
	reads a bare number.
	"""
	_require_fixture(site)

	label = labels.label_model(BATCH, warehouse=WAREHOUSE)

	assert label["transport_document_line"].startswith("UN 1263, FARBE, 3, III")
	assert label["adr_class_label"] == "Klasse 3 — Entzündbare flüssige Stoffe"
	assert label["packing_group_label"] == "Verpackungsgruppe III — geringer Gefährdungsgrad"
	# The TRGS 510 storage class stays a separate axis from the ADR transport class.
	assert label["storage_class"] == "3"
	assert label["storage_class_label"] == "Lagerklasse 3 — Entzündbare Flüssigkeiten"
	if label["expiry_date"]:
		assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", label["expiry_date"])


def test_tc_w3_021_printed_label_renders_the_same_model(site):
	"""TC-W3-021 (URS-W3-018 AC-1): screen preview and paper label share one template."""
	_require_fixture(site)

	html = labels.dispatch_label_html(BATCH, warehouse=WAREHOUSE)

	for expected in ("UN 1263", "FARBE", "III", BATCH, "kg", "Versandetikett Gefahrgut"):
		assert expected in html
	assert "Klasse 3 — Entzündbare flüssige Stoffe" in html


def test_tc_w3_021_scanner_path_resolves_the_handling_unit(site):
	"""TC-W3-021 step 1 (URS-W3-018 AC-1): scanning HU-000123 resolves through the existing
	W1/W2 scan resolver and yields the label data of the batch on the unit."""
	_require_fixture(site)
	if not site.db.get_value("Handling Unit", {"barcode": SCANNED_UNIT}):
		pytest.skip("handling-unit fixture not seeded on this site")

	resolved = dispatch.resolve_dispatch_scan(SCANNED_UNIT)

	assert resolved["recognised"] is True
	assert resolved["kind"] == "handling_unit"
	assert resolved["doctype"] == "Handling Unit"
	assert resolved["batch"]
	# A batch scan resolves through the shared resolver unchanged (one scan path).
	batch_scan = dispatch.resolve_dispatch_scan(BATCH)
	assert batch_scan["recognised"] is True
	assert batch_scan["batch"] == BATCH

	station = dispatch.scan_for_dispatch(SCANNED_UNIT)
	assert station["label_data"]["batch"] == station["batch"]
	assert station["label_data"]["handling_unit"] == station["name"]


def test_adr_vocabulary_is_the_regulated_one(site):
	"""URS-W3-018: ADR class and packing group are vocabularies, not free text.

	The transport classification (ADR Teil 2) is a different axis from the TRGS 510 storage
	class W2-7 maintains, so both are validated against their own list.
	"""
	assert contracts.validate_adr_class("3") == "3"
	assert contracts.validate_adr_class("4.1") == "4.1"
	assert contracts.validate_packing_group("iii") == "III"
	for invalid in ("", "10", "3.7", "Klasse 3"):
		with pytest.raises(contracts.HazmatDataError):
			contracts.validate_adr_class(invalid)
	for invalid in ("", "IV", "1"):
		with pytest.raises(contracts.HazmatDataError):
			contracts.validate_packing_group(invalid)
	assert contracts.shipping_name(" Farbe ") == "FARBE"


def test_dispatch_readiness_is_derived_on_the_profile(site):
	"""URS-W3-018: the profile itself shows whether dispatch would pass.

	`adr_dispatch_ready` is exactly the dispatch guard's verdict, mirrored read-only onto the
	profile so the technologist sees the gap before a lorry waits at the gate.
	"""
	_require_fixture(site)

	profile = frappe.get_doc("Hazmat Profile", PROFILE)
	assert profile.adr_dispatch_ready == 1
	assert profile.adr_class_designation == "Entzündbare flüssige Stoffe"

	profile.adr_packing_group = None
	profile.save()
	assert profile.adr_dispatch_ready == 0
	assert contracts.missing_adr_fields(profile.as_dict()) == ("adr_packing_group",)
