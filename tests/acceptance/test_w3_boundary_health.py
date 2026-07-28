"""TC-W3-017 — interface-health KPI drill-down and audited replay.

Verifies **URS-W3-014**: the health surface reports counts, error-queue depth and the oldest
unprocessed message (AC-1); B. Vogel reads one plain-language tile — *"ERP-Nachrichten mit
Handlungsbedarf: 1"* — that drills into the same dense queue rows, not a separate report
(AC-2); and P. Krüger's replay of the corrected message succeeds, is refused for an
unauthorised user naming the required permission, and is audited with actor, timestamp, message
reference and outcome (AC-3, URS-W3-021).
"""

from __future__ import annotations

import pytest
from test_w3_boundary_support import (
	ITEM,
	OPERATOR_USER,
	PLANNER_USER,
	RM_WAREHOUSE,
	VIEWER_USER,
	loopback,
)

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
contracts = pytest.importorskip("rheinwerk_mes.integration.boundary.contracts")
health = pytest.importorskip("rheinwerk_mes.integration.boundary.health")
inbound = pytest.importorskip("rheinwerk_mes.integration.boundary.inbound")
schema = pytest.importorskip("rheinwerk_mes.integration.boundary.schema")

UNKNOWN_ITEM = "erp-in-002-unknown-item.json"


@pytest.fixture
def rejected_message(site, monkeypatch):
	"""The precondition of TC-W3-017: exactly one rejected message from TC-W3-013 step 3."""
	site.db.delete("Boundary Message")
	site.db.delete("ERP Sales Input")
	loopback(monkeypatch)
	result = inbound.play_fixture(UNKNOWN_ITEM)
	assert result.outcome == contracts.REJECTED
	return result


def test_tc_w3_017_step_1_the_tile_reads_one_message_needing_attention(site, rejected_message):
	"""TC-W3-017 step 1 (URS-W3-014 AC-1/AC-2): with one rejected message the tile reads
	"ERP-Nachrichten mit Handlungsbedarf: 1" in plain language, and the metrics behind it name
	the error-queue depth and the oldest unprocessed message with a DD.MM.YYYY timestamp."""
	site.set_user(VIEWER_USER)

	tile = health.kpi_tile()
	assert tile["headline"] == "ERP-Nachrichten mit Handlungsbedarf: 1"
	assert tile["count"] == 1
	assert tile["tone"] == "red"
	assert tile["detail"].startswith("Fehlerwarteschlange: 1")

	numbers = health.metrics()
	assert numbers["error_queue_depth"] == 1
	assert numbers["hold_queue_depth"] == 0
	assert numbers["by_message_type"][contracts.ORDERS_IN][contracts.REJECTED] == 1
	oldest = numbers["oldest_unprocessed"]
	assert oldest["name"] == rejected_message.message
	assert len(oldest["first_seen_display"].split(" ")[0].split(".")) == 3
	assert oldest["age_hours"] >= 0


def test_tc_w3_017_step_1_the_tile_drills_into_the_same_queue_rows(site, rejected_message):
	"""TC-W3-017 step 1 (URS-W3-014 AC-2): the drill-down is a filter over the same
	`Boundary Message` data the tile counted — the dense row carries the machine-readable
	reason and its German-first label, not a separate report."""
	site.set_user(VIEWER_USER)
	tile = health.kpi_tile()
	assert tile["drilldown"]["doctype"] == contracts.MESSAGE_DOCTYPE
	assert tile["drilldown"]["filters"]["message_state"] == ["in", list(contracts.ATTENTION_STATUSES)]

	rows = health.queue()
	assert [row["name"] for row in rows] == [rejected_message.message]
	row = rows[0]
	assert row["reason_code"] == contracts.REASON_UNKNOWN_ITEM
	assert row["message_state"] == contracts.REJECTED
	assert row["first_seen_display"]

	surface = health.dashboard()
	assert surface["tile"]["count"] == len(surface["queue"]) == 1
	assert surface["labels"]["reasons"][contracts.REASON_UNKNOWN_ITEM]
	assert surface["labels"]["message_types"][contracts.ORDERS_IN]
	assert surface["metrics"]["contract_version"] == contracts.CONTRACT_VERSION


def test_tc_w3_017_step_2_the_planner_replays_the_corrected_message(site, rejected_message):
	"""TC-W3-017 step 2 (URS-W3-014 AC-3): after the master data is corrected, P. Krüger's
	replay processes the message, the demand appears, the queue empties and the audit names
	who replayed what, when and with which outcome."""
	payload = schema.fixture(UNKNOWN_ITEM)
	unknown = payload["demand"]["item_code"]
	item = site.get_doc("Item", ITEM).as_dict()
	site.get_doc(
		{
			"doctype": "Item",
			"item_code": unknown,
			"item_name": unknown,
			"item_group": item["item_group"],
			"stock_uom": item["stock_uom"],
		}
	).insert(ignore_permissions=True)

	site.set_user(PLANNER_USER)
	assert health.can_replay() is True

	outcome = health.replay(rejected_message.message)

	assert outcome["message_state"] == contracts.PROCESSED
	assert site.db.exists("ERP Sales Input", payload["external_order_ref"])
	assert health.metrics()["error_queue_depth"] == 0
	assert health.kpi_tile()["headline"] == "ERP-Nachrichten mit Handlungsbedarf: 0"
	assert health.kpi_tile()["tone"] == "green"

	trail = health.audit_trail(rejected_message.message)
	replayed = [entry for entry in trail if entry["gate"] == contracts.GATE_REPLAY]
	assert len(replayed) == 1
	assert replayed[0]["logged_by"] == PLANNER_USER
	assert replayed[0]["logged_at"]
	assert rejected_message.message.endswith(payload["message_id"])
	assert payload["message_id"] in replayed[0]["rule"]
	assert replayed[0]["outcome"] == audit.EXECUTED


def test_tc_w3_017_step_2_an_unauthorised_replay_is_refused_and_audited(site, rejected_message):
	"""TC-W3-017 step 2 (URS-W3-014 AC-3, URS-W3-023): the operator has no replay permission,
	so the attempt is refused naming the required role — and the refusal is audited."""
	site.set_user(OPERATOR_USER)
	assert health.can_replay() is False

	with pytest.raises(frappe.PermissionError) as refused:
		health.replay(rejected_message.message)
	assert "Rheinwerk Planner" in str(refused.value)

	trail = health.audit_trail(rejected_message.message)
	refusals = [
		entry
		for entry in trail
		if entry["gate"] == contracts.GATE_REPLAY and entry["outcome"] == audit.REFUSED
	]
	assert len(refusals) == 1
	assert refusals[0]["logged_by"] == OPERATOR_USER
	assert OPERATOR_USER in (refusals[0]["detail"] or "")


def test_tc_w3_017_replaying_a_held_posting_touches_only_that_message(site, monkeypatch):
	"""TC-W3-017 step 2 (URS-W3-014 AC-3, URS-W3-012 AC-2): a held GL posting is replayed
	individually — the second held posting of the same unmapped warehouse stays held."""
	site.db.delete("Boundary Message")
	endpoint = loopback(monkeypatch)

	from rheinwerk_mes.integration.boundary import gl, queues

	held = []
	for index in (1, 2):
		payload = {
			**schema.fixture("gl-out-002-unmapped-warehouse.json"),
			"message_id": f"GL-HOLD-{index}",
		}
		held.append(
			queues.record(
				payload,
				message_state=contracts.HELD,
				reason_code=contracts.REASON_UNMAPPED_WAREHOUSE,
				reason=f"{RM_WAREHOUSE} {contracts.ACCOUNT_MAP_DOCTYPE}",
				warehouse=payload["warehouse"],
				gate=contracts.GATE_OUTBOUND,
			)
		)
	assert health.metrics()["hold_queue_depth"] == 2

	site.get_doc(
		{
			"doctype": contracts.ACCOUNT_MAP_DOCTYPE,
			"warehouse": payload["warehouse"],
			"company": "Rheinwerk Chemie GmbH",
			"currency": "EUR",
			"stock_account_code": "1300-ROHSTOFFE",
			"offset_account_code": "5900-BESTANDSVERAENDERUNG",
		}
	).insert(ignore_permissions=True)

	site.set_user(PLANNER_USER)
	outcome = health.replay(held[0])

	assert outcome["message_state"] == contracts.DELIVERED
	assert len(endpoint.messages(contracts.GL_POSTING_OUT)) == 1
	assert health.metrics()["hold_queue_depth"] == 1
	assert site.db.get_value("Boundary Message", held[1], "message_state") == contracts.HELD
	assert gl.account_map(payload["warehouse"]) is not None


def test_tc_w3_017_replay_all_needs_the_same_permission(site, rejected_message):
	"""TC-W3-017 step 2 (URS-W3-014 AC-3): bulk replay of the outbox is gated by the same
	permission as a single replay."""
	site.set_user(OPERATOR_USER)
	with pytest.raises(frappe.PermissionError):
		health.replay_all()

	site.set_user(PLANNER_USER)
	assert health.replay_all(contracts.CONFIRMATION_OUT) == {"delivered": 0, "queued": 0}
