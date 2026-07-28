"""TC-W2-022 / TC-W2-023 — inspector queue and rejection disposition (W2-4).

Verifies **URS-W2-015 AC-1…3** (Work Queue → Detail: filterable rows with batch chip, item
and type; reading inputs carrying their unit and limit; a directive empty state) and
**URS-W2-016 AC-1/AC-2** (a Rejected inspection offers Block batch / Assign rework, both
requiring a reason, and an undispositioned rejection is reported by the integrity check).
"""

from __future__ import annotations

import pytest
from test_w2_quality_support import (
	BATCH_C1,
	BATCH_C2,
	COMPOUND_ITEM,
	FAILING_READINGS,
	FIRST_ORDER,
	PASSING_READINGS,
	VISCOSITY,
	inspection_for,
	require_fixture,
	require_quality_schema,
	set_qa_state,
)

pytest.importorskip("frappe")
queue = pytest.importorskip("rheinwerk_mes.quality.queue")
disposition = pytest.importorskip("rheinwerk_mes.quality.disposition")
inspections = pytest.importorskip("rheinwerk_mes.quality.inspections")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")


@pytest.fixture
def quality_site(site):
	require_quality_schema(site)
	for batch in (BATCH_C1, BATCH_C2):
		require_fixture(site, "Batch", batch)
		set_qa_state(site, batch, qa_state.QUARANTINED)
	return site


def test_queue_lists_due_inspections_with_batch_chip_item_and_type(quality_site):
	"""URS-W2-015 AC-1 / TC-W2-022 step 1 — both batches are due, with their chips."""
	inspection_for(quality_site, BATCH_C1, work_order=FIRST_ORDER)
	inspection_for(quality_site, BATCH_C2)

	model = queue.inspection_queue()

	rows = {row["batch"]: row for row in model["rows"]}
	assert {BATCH_C1, BATCH_C2} <= set(rows)
	row = rows[BATCH_C1]
	assert row["item"] == COMPOUND_ITEM
	assert row["type_label"] == "Fertigungsbegleitend"
	assert row["chip"]["qa_state_label"] == "Quarantäne"
	assert row["production_order"] == FIRST_ORDER


def test_queue_is_filterable_by_type_item_batch_and_production_order(quality_site):
	"""URS-W2-015 AC-1 — every documented filter axis narrows the queue."""
	inspection_for(quality_site, BATCH_C1, work_order=FIRST_ORDER)
	inspection_for(quality_site, BATCH_C2)

	assert [row["batch"] for row in queue.inspection_queue(batch=BATCH_C2)["rows"]] == [BATCH_C2]
	assert [row["batch"] for row in queue.inspection_queue(production_order=FIRST_ORDER)["rows"]] == [
		BATCH_C1
	]
	assert queue.inspection_queue(inspection_type=inspections.INCOMING)["rows"] == []
	assert {row["item"] for row in queue.inspection_queue(item=COMPOUND_ITEM)["rows"]} == {COMPOUND_ITEM}


def test_detail_pane_renders_units_and_limits_next_to_every_reading(quality_site):
	"""URS-W2-015 AC-2 / TC-W2-022 step 2 — unit suffix and specification per input."""
	doc = inspection_for(quality_site, BATCH_C1)

	detail = queue.inspection_detail(doc.name)

	viscosity = next(row for row in detail["readings"] if row["parameter"] == VISCOSITY)
	assert viscosity["unit_suffix"] == "mPa·s"
	assert viscosity["limit_text"] == "1200 – 1400 mPa·s"
	assert detail["chip"]["batch"] == BATCH_C1


def test_failed_submit_preserves_the_entered_values(quality_site):
	"""URS-W2-015 AC-2 / TC-W2-022 step 2 — a refused submit does not discard readings."""
	doc = inspection_for(quality_site, BATCH_C1, PASSING_READINGS)
	quality_site.db.set_value("Quality Inspection", doc.name, "inspected_by", None)

	with pytest.raises(Exception):
		inspections.enter_readings(doc.name, {VISCOSITY: ""}, submit=True)

	detail = queue.inspection_detail(doc.name)
	assert {row["parameter"]: row["reading"] for row in detail["readings"]}[VISCOSITY] == "1290"


def test_empty_queue_directs_to_the_next_scheduled_inspection(quality_site):
	"""URS-W2-015 AC-3 / TC-W2-022 step 3 — the empty state directs, never decorates."""
	set_qa_state(quality_site, BATCH_C1, qa_state.RELEASED)
	set_qa_state(quality_site, BATCH_C2, qa_state.RELEASED)

	model = queue.inspection_queue()

	assert model["rows"] == []
	assert model["empty_state"]["title"] == "Keine Prüfungen fällig"
	assert model["empty_state"]["hint"].startswith("Nächste geplante Prüfung")


def test_rejected_inspection_offers_both_dispositions(quality_site):
	"""URS-W2-016 AC-1 / TC-W2-023 step 1 — Block batch and Assign rework, in German."""
	doc = inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	detail = queue.inspection_detail(doc.name)

	assert detail["disposition"]["required"] is True
	assert [choice["label"] for choice in detail["disposition"]["choices"]] == [
		"Charge sperren",
		"Nacharbeit zuweisen",
	]


def test_disposition_without_a_reason_is_refused(quality_site):
	"""URS-W2-016 AC-1 — a reason is mandatory for either decision."""
	doc = inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	with pytest.raises(Exception):
		disposition.record_disposition(doc.name, disposition.BLOCK_BATCH, "")


def test_block_batch_disposition_drives_qa_state_through_the_genealogy_api(quality_site):
	"""URS-W2-016 AC-1 — the decision blocks the batch, audited to the inspection."""
	doc = inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	result = disposition.record_disposition(doc.name, disposition.BLOCK_BATCH, "Viskosität zu hoch")

	assert result["qa_state"] == qa_state.BLOCKED
	assert quality_site.db.get_value("Batch", BATCH_C2, "qa_state") == qa_state.BLOCKED
	history = qa_state.state_history(BATCH_C2)
	assert history[-1]["triggering_document"] == doc.name


def test_rework_disposition_records_the_rework_order(quality_site):
	"""URS-W2-016 AC-1 — rework keeps the batch traceable to its rework order."""
	doc = inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	disposition.record_disposition(
		doc.name, disposition.ASSIGN_REWORK, "Nachmischen", rework_order=FIRST_ORDER
	)

	assert quality_site.db.get_value("Quality Inspection", doc.name, "rw_rework_order") == FIRST_ORDER


def test_integrity_check_reports_rejections_without_a_disposition(quality_site):
	"""URS-W2-016 AC-2 / TC-W2-023 step 2 — "Abgelehnt ohne Verwendungsentscheid"."""
	doc = inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	findings = {row["name"]: row for row in disposition.undispositioned_rejections()}
	assert doc.name in findings
	assert findings[doc.name]["finding"] == "Abgelehnt ohne Verwendungsentscheid"

	disposition.record_disposition(doc.name, disposition.BLOCK_BATCH, "Viskosität zu hoch")
	assert doc.name not in {row["name"] for row in disposition.undispositioned_rejections()}


def test_undispositioned_rejection_blocks_release_of_the_batch(quality_site):
	"""URS-W2-016 AC-2 — the qa_state gate refuses release until QA has decided."""
	inspection_for(quality_site, BATCH_C2, FAILING_READINGS, submit=True)

	with pytest.raises(Exception):
		qa_state.transition(BATCH_C2, qa_state.RELEASED, reason="Freigabe versucht")
