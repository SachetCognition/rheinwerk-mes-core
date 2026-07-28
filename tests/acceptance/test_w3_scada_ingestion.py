"""TC-W3-018 — OPC-UA tracking-event ingestion and the unmatched-events queue.

Verifies **URS-W3-015** (process-control events attached to the right order and operation
within 5 s, attributed to source "OPC-UA" and never to an operator; an event for a work
centre with no In-Progress order held in an unmatched-events queue, never dropped) and
**URS-W3-021** (every OPC-UA-sourced tracking event audited through the W1 gate audit with
the source system as actor) through **TC-W3-018** of
`docs/test/TST-W3-planning-boundary.md`.
"""

from __future__ import annotations

import pytest
from test_w3_scada_support import (
	FIRST_ORDER,
	MIX,
	TAG_FILL_PRODUCED,
	TAG_MIX_PRODUCED,
	ensure_tag_mappings,
	park_work_centre,
	running_order,
	tag_event,
)

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
contracts = pytest.importorskip("rheinwerk_mes.integration.scada.contracts")
ingest = pytest.importorskip("rheinwerk_mes.integration.scada.ingest")
unmatched = pytest.importorskip("rheinwerk_mes.integration.scada.unmatched")

from rheinwerk_mes.integration.scada.adapter import ScadaAdapter  # noqa: E402
from rheinwerk_mes.integration.scada.buffer import SpoolBuffer  # noqa: E402
from rheinwerk_mes.integration.scada.transport import SimulatedTransport  # noqa: E402


def test_produced_count_lands_on_the_running_operation(site):
	"""URS-W3-015 AC-1 / TC-W3-018 step 1 — 25 kg on PO-2026-0001's MIX, source OPC-UA."""
	ensure_tag_mappings(site)
	order = running_order(site)

	doc = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))

	assert doc.work_order == order.name == FIRST_ORDER
	assert doc.operation == MIX
	assert doc.work_centre_code == "LINE-1/MIX-01"
	assert doc.value == 25
	assert doc.event_type == contracts.EVENT_PRODUCED_COUNT
	assert doc.event_state == contracts.STATE_PROCESSED
	assert doc.source_system == contracts.SOURCE_SYSTEM
	assert doc.processing_seconds < contracts.ATTACHMENT_BUDGET_SECONDS


def test_the_event_is_never_attributed_to_an_operator(site):
	"""URS-W3-015 AC-1 — machine-reported work credits the source system, no employee."""
	ensure_tag_mappings(site)
	running_order(site)

	doc = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))

	assert doc.source_system == contracts.SOURCE_SYSTEM
	employees = site.get_all("Job Card Time Log", filters={"parent": doc.job_card}, pluck="employee")
	assert not [employee for employee in employees if employee]


def test_every_event_is_audited_with_the_source_system_as_actor(site):
	"""URS-W3-021 / TC-W3-018 — the W1 gate audit carries the OPC-UA event and its actor."""
	ensure_tag_mappings(site)
	running_order(site)

	doc = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))
	entries = audit.entries_for(ingest.EVENT_DOCTYPE, doc.name)

	assert len(entries) == 1
	assert entries[0]["gate"] == ingest.GATE
	assert entries[0]["outcome"] == audit.EXECUTED
	assert entries[0]["logged_by"] == contracts.SOURCE_SYSTEM_USER
	assert FIRST_ORDER in entries[0]["detail"]


def test_event_without_an_in_progress_order_is_held_for_disposition(site):
	"""URS-W3-015 AC-2 / TC-W3-018 step 2 — FILL-01 has no running order: queued, not lost."""
	ensure_tag_mappings(site)
	running_order(site)
	park_work_centre(site, "FILL-01")

	doc = ingest.ingest(tag_event(TAG_FILL_PRODUCED, 12, "2026-06-15 08:45:00", sequence=2))

	assert doc.event_state == contracts.STATE_UNMATCHED
	assert not doc.work_order
	assert doc.work_centre_code == "LINE-1/FILL-01"
	assert "LINE-1/FILL-01" in doc.unmatched_reason

	queue = unmatched.queue()
	assert doc.name in [row["name"] for row in queue["rows"]]
	assert queue["depth"] >= 1
	assert audit.entries_for(ingest.EVENT_DOCTYPE, doc.name)


def test_an_unmapped_tag_is_held_too(site):
	"""URS-W3-015 AC-2 — an event on an unmapped node is queued, never silently dropped."""
	ensure_tag_mappings(site)
	running_order(site)

	doc = ingest.ingest(tag_event("ns=2;s=Line9.Xx99.ProducedKg", 5, "2026-06-15 09:00:00"))

	assert doc.event_state == contracts.STATE_UNMATCHED
	assert "ns=2;s=Line9.Xx99.ProducedKg" in doc.unmatched_reason


def test_held_event_can_be_assigned_to_an_order(site):
	"""URS-W3-015 AC-2 / TC-W3-018 step 2 — the planner attaches a held event to an order."""
	ensure_tag_mappings(site)
	order = running_order(site)
	site.db.set_value("Work Order", order.name, "exec_state", "Interrupted", update_modified=False)
	doc = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))
	assert doc.event_state == contracts.STATE_UNMATCHED
	site.db.set_value("Work Order", order.name, "exec_state", "In Progress", update_modified=False)

	result = unmatched.assign_to_order(doc.name, order.name, note="Anlagenmeldung nachgetragen")

	assert result["event_state"] == contracts.STATE_ASSIGNED
	doc.reload()
	assert doc.work_order == order.name
	assert doc.operation == MIX and doc.job_card
	assert doc.dispositioned_by and doc.dispositioned_at
	assert len(audit.entries_for(ingest.EVENT_DOCTYPE, doc.name)) == 2


def test_held_event_can_be_discarded_with_a_reason(site):
	"""URS-W3-015 AC-2 / TC-W3-018 step 2 — a discarded event survives, it is never dropped."""
	ensure_tag_mappings(site)
	order = running_order(site)
	park_work_centre(site, "FILL-01")
	doc = ingest.ingest(tag_event(TAG_FILL_PRODUCED, 12, "2026-06-15 08:45:00", sequence=2))

	result = unmatched.discard(doc.name, "Reinigungslauf der Abfüllung")

	assert result["event_state"] == contracts.STATE_DISCARDED
	assert doc.name not in [row["name"] for row in unmatched.queue()["rows"]]
	assert site.db.exists(ingest.EVENT_DOCTYPE, doc.name), "a dispositioned event is never deleted"

	mix_event = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))
	assert mix_event.work_order == order.name


def test_the_committed_fixture_script_runs_end_to_end(site, tmp_path):
	"""URS-W3-015 / TC-W3-018 — the committed simulator drives the whole SCADA path."""
	ensure_tag_mappings(site)
	order = running_order(site)
	park_work_centre(site, "FILL-01")
	adapter = ScadaAdapter(SimulatedTransport.from_fixture(), buffer=SpoolBuffer(tmp_path / "spool.jsonl"))

	docs = adapter.pump()

	assert len(docs) == 6
	matched = [doc for doc in docs if doc.event_state == contracts.STATE_PROCESSED]
	held = [doc for doc in docs if doc.event_state == contracts.STATE_UNMATCHED]
	assert len(matched) == 5 and len(held) == 1
	assert {doc.work_order for doc in matched} == {order.name}
	assert held[0].work_centre_code == "LINE-1/FILL-01"
	assert site.get_doc("Job Card", matched[-1].job_card).total_completed_qty == 75.0


def test_events_are_refused_for_an_order_that_is_not_in_progress(site):
	"""URS-W3-015 — only an In-Progress order takes events (docs/design/W1-exec-state.md)."""
	ensure_tag_mappings(site)
	order = running_order(site)
	site.db.set_value("Work Order", order.name, "exec_state", "Interrupted", update_modified=False)

	doc = ingest.ingest(tag_event(TAG_MIX_PRODUCED, 25, "2026-06-15 08:10:00", sequence=1))

	assert doc.event_state == contracts.STATE_UNMATCHED
	assert not doc.work_order
