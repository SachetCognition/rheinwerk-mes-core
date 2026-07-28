"""TC-W3-025 — audit completeness across the four W3 audit classes.

Verifies **URS-W3-021** (schedule decisions, capacity refusals, boundary message rejection and
replay, and OPC-UA ingestion each leave an audit record naming actor/source, timestamp, action,
record reference and outcome — and that no update path exists) through **TC-W3-025** of
`docs/test/TST-W3-planning-boundary.md`.

Each class is triggered through its published API — never by writing the log directly — and
then read back from the `Execution Gate Log`, the single audit surface the estate shares since
W1. The immutability half is asserted against the DocType contract *and* by attempting a write
through the document API, because a read-only field the server ignores is not a control.
"""

from __future__ import annotations

from typing import Any

import pytest
from test_w3_boundary_support import loopback
from test_w3_scada_support import TAG_MIX_PRODUCED, ensure_tag_mappings, running_order, tag_event
from test_w3_scheduling_support import (
	FIRST_ORDER,
	LINE,
	OPERATOR_USER,
	as_planner,
	draft_schedule,
	gate_log,
)

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

#: Every audit entry answers these, whatever act produced it (URS-W3-021 AC-1). The record
#: reference is asserted separately, because it is the filter the entry is read back by.
ENTRY_FIELDS = ("gate", "rule", "outcome", "logged_by", "logged_at")

EQUIPMENT_TIMESTAMP = "2026-03-02T07:15:00"


def _complete(entry: dict[str, Any]) -> bool:
	return all(entry.get(field) for field in ENTRY_FIELDS)


def _latest(gate: str) -> dict[str, Any] | None:
	rows = frappe.get_all(
		audit.LOG_DOCTYPE,
		filters={"gate": gate},
		fields=list(ENTRY_FIELDS) + ["detail", "name"],
		order_by="creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def test_schedule_approval_is_audited(site):
	"""URS-W3-021 AC-1 / TC-W3-025 class 1 — approving a Linienplan names actor and outcome."""
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	schedule = draft_schedule(site)
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Wochenplan KW 10")

	entries = gate_log(site, lifecycle.GATE, schedule.name)
	assert entries, "the approval left no audit entry"
	assert entries[0]["outcome"] == audit.EXECUTED
	assert entries[0]["to_state"] == lifecycle.APPROVED
	assert _complete(_latest(lifecycle.GATE) or {})


def test_capacity_refusal_is_audited(site):
	"""URS-W3-021 AC-1 / TC-W3-025 class 2 — a refused slot is logged, never toast-only."""
	from rheinwerk_mes.manufacturing_core.scheduling import capacity, lifecycle

	schedule = draft_schedule(site)
	as_planner(site)
	lifecycle.approve(schedule.name)
	second = draft_schedule(site, work_orders=[FIRST_ORDER])
	as_planner(site)

	with pytest.raises(frappe.ValidationError):
		lifecycle.approve(second.name)

	entry = _latest(capacity.GATE)
	assert entry, "the capacity refusal left no audit entry"
	assert entry["outcome"] == audit.REFUSED
	assert _complete(entry)
	assert LINE in entry["detail"] or LINE in entry["rule"]


def test_boundary_rejection_and_replay_are_audited(site, monkeypatch):
	"""URS-W3-021 AC-1 / TC-W3-025 class 3 — the rejected message and its replay both audit."""
	from rheinwerk_mes.integration.boundary import contracts, health, inbound

	loopback(monkeypatch)
	rejected = inbound.play_fixture("erp-in-002-unknown-item.json")
	assert rejected.outcome == contracts.REJECTED

	message = frappe.get_all(
		contracts.MESSAGE_DOCTYPE,
		filters={"message_state": contracts.REJECTED},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	assert message, "the rejection stored no message to replay"
	trail = health.audit_trail(message[0])
	assert trail and _complete(trail[-1])

	with pytest.raises(frappe.PermissionError):
		site.set_user(OPERATOR_USER)
		health.replay(message[0])
	site.set_user("Administrator")

	refusals = [entry for entry in health.audit_trail(message[0]) if entry["outcome"] == audit.REFUSED]
	assert refusals, "the unauthorised replay attempt left no audit entry"
	assert _complete(refusals[-1])


def test_opc_ua_event_is_audited_with_its_source(site):
	"""URS-W3-021 AC-1 / TC-W3-025 class 4 — an ingested event names OPC-UA as the actor."""
	from rheinwerk_mes.integration.scada import ingest

	ensure_tag_mappings(site)
	running_order(site)
	event = tag_event(TAG_MIX_PRODUCED, 25.0, EQUIPMENT_TIMESTAMP, sequence=1)
	doc = ingest.ingest(event)

	entries = audit.entries_for(ingest.EVENT_DOCTYPE, doc.name)
	assert entries, "the ingested event left no audit entry"
	assert _complete(entries[-1])
	assert entries[-1]["gate"] == ingest.GATE
	assert TAG_MIX_PRODUCED in entries[-1]["detail"], "the entry must name the tag it came from"
	assert FIRST_ORDER in entries[-1]["detail"], "the entry must name the order it was booked on"
	assert "opcua" in entries[-1]["logged_by"], "the equipment, not a human, is the actor here"


def test_audit_records_cannot_be_modified(site):
	"""URS-W3-021 AC-2 / TC-W3-025 step 2 — the log is append-only for every role."""
	meta = frappe.get_meta(audit.LOG_DOCTYPE)
	assert not any(permission.write for permission in meta.permissions), (
		"no role may hold write permission on the audit log"
	)

	schedule = draft_schedule(site)
	as_planner(site)
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	lifecycle.approve(schedule.name)
	entry = _latest(lifecycle.GATE)
	assert entry

	doc = frappe.get_doc(audit.LOG_DOCTYPE, entry["name"])
	doc.outcome = audit.REFUSED
	with pytest.raises(frappe.PermissionError):
		doc.save()
