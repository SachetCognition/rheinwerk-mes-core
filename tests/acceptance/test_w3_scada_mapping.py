"""TC-W3-019 — tag-mapping administration and its validation.

Verifies **URS-W3-016** (technologist-maintained mapping of OPC-UA node addresses to work
centres (CDM-08) and event types, refusing a mapping to a non-existent work centre and
naming the invalid code) through **TC-W3-019** of `docs/test/TST-W3-planning-boundary.md`.
The mono rendering of the tag identifiers in the Desk admin table is asserted on the
committed list-view assets, so it holds without a browser.
"""

from __future__ import annotations

import pytest
from test_w3_scada_support import (
	MIX,
	TAG_MIX_PRODUCED,
	ensure_tag_mappings,
	running_order,
	tag_event,
)

frappe = pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.integration.scada.contracts")
ingest = pytest.importorskip("rheinwerk_mes.integration.scada.ingest")
mapping = pytest.importorskip("rheinwerk_mes.integration.scada.mapping")

TECHNOLOGIST_USER = "t.schmid@rheinwerk-chemie.example"
INVALID_WORK_CENTRE = "LINE-9/XX-99"


def test_technologist_maps_a_tag_to_a_work_centre_and_events_resolve(site):
	"""URS-W3-016 AC-1 / TC-W3-019 step 1 — the mapped tag resolves to LINE-1/MIX-01."""
	ensure_tag_mappings(site)
	order = running_order(site)
	if site.db.exists("User", TECHNOLOGIST_USER):
		site.set_user(TECHNOLOGIST_USER)

	doc = mapping.upsert_mapping(
		tag_address=TAG_MIX_PRODUCED,
		work_centre_code="LINE-1/MIX-01",
		event_type=contracts.EVENT_PRODUCED_COUNT,
	)

	assert doc.work_centre == "MIX-01"
	assert doc.production_line == "LINE-1"
	resolved = mapping.mapping_for_tag(TAG_MIX_PRODUCED)
	assert resolved["work_centre_code"] == "LINE-1/MIX-01"
	assert resolved["event_type"] == contracts.EVENT_PRODUCED_COUNT

	site.set_user("Administrator")
	event = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))
	assert (event.work_order, event.operation) == (order.name, MIX)


def test_mapping_to_a_non_existent_work_centre_is_refused_naming_the_code(site):
	"""URS-W3-016 AC-2 / TC-W3-019 step 2 — save refused, naming LINE-9/XX-99."""
	ensure_tag_mappings(site)

	with pytest.raises(frappe.ValidationError) as refusal:
		mapping.upsert_mapping(
			tag_address="ns=2;s=Line9.Xx99.ProducedKg",
			work_centre_code=INVALID_WORK_CENTRE,
			event_type=contracts.EVENT_PRODUCED_COUNT,
		)

	assert INVALID_WORK_CENTRE in str(refusal.value)
	assert not mapping.mapping_for_tag("ns=2;s=Line9.Xx99.ProducedKg")


def test_a_work_centre_of_another_line_is_refused(site):
	"""URS-W3-016 AC-2 — a work centre that belongs to another line is not silently accepted."""
	ensure_tag_mappings(site)
	site.get_doc(
		{"doctype": "Production Line", "production_line_name": "LINE-9", "division": "Werk Nord"}
	).insert(ignore_permissions=True)

	with pytest.raises(frappe.ValidationError) as refusal:
		mapping.upsert_mapping(
			tag_address="ns=2;s=Line9.Mix01.ProducedKg",
			work_centre_code="LINE-9/MIX-01",
			event_type=contracts.EVENT_PRODUCED_COUNT,
		)

	assert "LINE-9/MIX-01" in str(refusal.value)
	assert "LINE-1" in str(refusal.value)


def test_an_unknown_event_type_is_refused(site):
	"""URS-W3-016 — the event-type vocabulary is closed (produced-count/start/stop)."""
	ensure_tag_mappings(site)

	with pytest.raises(frappe.ValidationError):
		mapping.upsert_mapping(
			tag_address="ns=2;s=Line1.Mix01.Temperature",
			work_centre_code="LINE-1/MIX-01",
			event_type="temperature",
		)


def test_seeded_mappings_cover_the_line_1_fixture(site):
	"""URS-W3-016 AC-1 — LINE-1/MIX-01 and LINE-1/FILL-01 ship as committed fixtures."""
	ensure_tag_mappings(site)

	assert {row["tag_address"] for row in mapping.mappings_of_work_centre("LINE-1/MIX-01")} == {
		"ns=2;s=Line1.Mix01.ProducedKg",
		"ns=2;s=Line1.Mix01.OperationStart",
		"ns=2;s=Line1.Mix01.OperationStop",
	}
	assert mapping.mappings_of_work_centre("LINE-1/FILL-01")


def test_admin_table_renders_tag_identifiers_in_mono(repo_root):
	"""URS-W3-016 / TC-W3-019 — mono identifiers in the Desk mapping table (design skill)."""
	listview = (
		repo_root / "rheinwerk_mes/integration/doctype/opc_ua_tag_mapping/opc_ua_tag_mapping_list.js"
	).read_text(encoding="utf-8")

	assert "tag_address(value)" in listview
	assert "work_centre_code(value)" in listview
	assert "IBM Plex Mono" in listview
	assert "tabular-nums" in listview
	assert "__(" in listview, "every label in the admin table is translated"
