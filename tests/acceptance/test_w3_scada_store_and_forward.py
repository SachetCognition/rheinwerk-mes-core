"""TC-W3-020 — store-and-forward across an adapter↔MES outage.

Verifies **URS-W3-017** (events buffered during connectivity loss, delivered in order on
reconnection, flagged late with their original equipment timestamp) through **TC-W3-020** of
`docs/test/TST-W3-planning-boundary.md`. The buffer half runs offline — it is adapter-side
code and must work exactly when the MES is unreachable.
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

from rheinwerk_mes.integration.scada.adapter import ScadaAdapter
from rheinwerk_mes.integration.scada.buffer import SpoolBuffer
from rheinwerk_mes.integration.scada.contracts import TagEvent
from rheinwerk_mes.integration.scada.transport import SimulatedTransport

#: The three produced counts the mixer publishes during the 10-minute outage.
OUTAGE_EVENTS = (
	("2026-06-15 08:10:00", 25.0, 1),
	("2026-06-15 08:20:00", 25.0, 2),
	("2026-06-15 08:30:00", 25.0, 3),
)


def _outage_events() -> list[TagEvent]:
	return [tag_event(TAG_MIX_PRODUCED, value, stamp, sequence) for stamp, value, sequence in OUTAGE_EVENTS]


def test_buffer_keeps_order_and_survives_the_outage_offline(tmp_path):
	"""URS-W3-017 AC-1 / TC-W3-020 step 1 — nothing is lost at the adapter, order preserved."""
	spool = SpoolBuffer(tmp_path / "spool.jsonl")
	adapter = ScadaAdapter(SimulatedTransport(_outage_events()), buffer=spool, sink=lambda *_a, **_k: None)
	adapter.disconnect()

	adapter.pump()

	assert adapter.buffered == 3
	reopened = SpoolBuffer(tmp_path / "spool.jsonl")
	assert [event.sequence for event in reopened.events()] == [1, 2, 3]
	assert [event.equipment_timestamp for event in reopened.events()] == [
		stamp for stamp, _value, _sequence in OUTAGE_EVENTS
	]


def test_a_failed_replay_leaves_the_spool_intact(tmp_path):
	"""URS-W3-017 — a replay that cannot be delivered keeps every buffered event."""
	spool = SpoolBuffer(tmp_path / "spool.jsonl")
	for event in _outage_events():
		spool.append(event)

	def failing_sink(_event, late=False):
		raise RuntimeError("MES nicht erreichbar")

	adapter = ScadaAdapter(SimulatedTransport([]), buffer=spool, sink=failing_sink)
	with pytest.raises(RuntimeError):
		adapter.replay()

	assert spool.depth() == 3


def test_replay_delivers_three_events_in_order_flagged_late(site, tmp_path):
	"""URS-W3-017 AC-1 / TC-W3-020 step 2 — 3/3 on PO-2026-0001, original stamps, late flag."""
	ensure_tag_mappings(site)
	order = running_order(site)
	adapter = ScadaAdapter(SimulatedTransport(_outage_events()), buffer=SpoolBuffer(tmp_path / "spool.jsonl"))

	adapter.disconnect()
	adapter.pump()
	assert adapter.buffered == 3, "the adapter holds the events while the MES is unreachable"

	delivered = adapter.connect()

	assert len(delivered) == 3
	assert adapter.buffered == 0
	assert [doc.sequence for doc in delivered] == [1, 2, 3]
	assert [str(doc.equipment_timestamp) for doc in delivered] == [
		"2026-06-15 08:10:00",
		"2026-06-15 08:20:00",
		"2026-06-15 08:30:00",
	]
	assert all(doc.is_late == 1 for doc in delivered)
	assert all(doc.work_order == order.name and doc.operation == MIX for doc in delivered)


def test_replayed_counts_book_their_cumulative_output(site, tmp_path):
	"""URS-W3-017 / URS-W3-015 — the replayed counts reach the order's recorded output."""
	ensure_tag_mappings(site)
	order = running_order(site)
	adapter = ScadaAdapter(SimulatedTransport(_outage_events()), buffer=SpoolBuffer(tmp_path / "spool.jsonl"))
	adapter.disconnect()
	adapter.pump()

	delivered = adapter.connect()

	card = site.get_doc("Job Card", delivered[-1].job_card)
	assert card.total_completed_qty == 75.0
	assert site.db.get_value("Work Order", order.name, "exec_state") == "In Progress"


def test_live_delivery_is_not_flagged_late(site, tmp_path):
	"""URS-W3-017 — only replayed events carry the late flag."""
	ensure_tag_mappings(site)
	running_order(site)
	adapter = ScadaAdapter(
		SimulatedTransport(_outage_events()[:1]), buffer=SpoolBuffer(tmp_path / "spool.jsonl")
	)

	delivered = adapter.pump()

	assert len(delivered) == 1
	assert delivered[0].is_late == 0
