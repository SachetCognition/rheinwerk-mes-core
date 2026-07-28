"""TC-W3-014 — confirmations out on Completed, with a durable queue across an outage.

Verifies **URS-W3-011**: completing a production order emits exactly one schema-valid
confirmation naming the group-ERP order reference, the produced item, the produced quantity and
the finished-goods batch ids (AC-1); while the endpoint is unreachable the message is queued,
visible as backlog on the health surface and delivered exactly once on recovery — no loss, no
duplication (AC-2).

Delivery goes through the injected loopback transport, so W4 can point the same emitter at a
real endpoint without touching this behaviour.
"""

from __future__ import annotations

import pytest
from test_w3_boundary_support import (
	EXTERNAL_REF,
	FIRST_ORDER,
	ITEM,
	QUANTITY,
	SECOND_ORDER,
	book_production,
	clear_messages,
	complete,
	loopback,
	messages,
	submitted_order,
)

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
contracts = pytest.importorskip("rheinwerk_mes.integration.boundary.contracts")
health = pytest.importorskip("rheinwerk_mes.integration.boundary.health")
outbound = pytest.importorskip("rheinwerk_mes.integration.boundary.outbound")
schema = pytest.importorskip("rheinwerk_mes.integration.boundary.schema")


@pytest.fixture
def endpoint(site, monkeypatch):
	"""A fresh loopback endpoint and an empty message store for one test."""
	clear_messages(site)
	return loopback(monkeypatch)


def confirmations(site, **filters):
	return messages(site, contracts.CONFIRMATION_OUT, **filters)


def test_tc_w3_014_step_1_completing_an_order_emits_exactly_one_confirmation(site, endpoint):
	"""TC-W3-014 step 1 (URS-W3-011 AC-1): completing PO-2026-0001 (500 kg) emits one
	schema-valid confirmation carrying GRP-SO-77001, RW-CHM-0003, 500 kg and the FG batch the
	manufacture receipt created — and completing is what triggers it, not a manual call."""
	order = submitted_order(site, FIRST_ORDER)
	book_production(site, order)

	complete(site, order)

	stored = confirmations(site)
	assert len(stored) == 1, "exactly one confirmation per completion"
	assert stored[0]["message_state"] == contracts.DELIVERED
	assert stored[0]["message_id"] == f"CONF-{FIRST_ORDER}"

	assert len(endpoint.messages(contracts.CONFIRMATION_OUT)) == 1
	payload = endpoint.messages(contracts.CONFIRMATION_OUT)[0]
	assert schema.validate_message(payload) is payload
	assert payload["external_order_ref"] == EXTERNAL_REF
	assert payload["item_code"] == ITEM
	assert payload["produced_quantity"] == QUANTITY
	assert payload["uom"] == "Kg"
	assert payload["batches"], "the confirmation names the FG batches (CDM-03)"

	trail = audit.entries_for("Boundary Message", stored[0]["name"])
	assert [entry["outcome"] for entry in trail] == [audit.EXECUTED, audit.EXECUTED]
	assert trail[-1]["to_state"] == contracts.DELIVERED


def test_tc_w3_014_step_1_a_second_save_of_a_completed_order_emits_nothing_more(site, endpoint):
	"""TC-W3-014 step 1 (URS-W3-011 AC-1): the confirmation is keyed by the order, so any
	further write to an already completed order never produces a second message."""
	order = submitted_order(site, FIRST_ORDER)
	book_production(site, order)
	complete(site, order)

	order.reload()
	order.flags.ignore_permissions = True
	order.save()
	outbound.on_work_order_update(order)

	assert len(confirmations(site)) == 1
	assert len(endpoint.messages(contracts.CONFIRMATION_OUT)) == 1


def test_tc_w3_014_step_2_an_unreachable_endpoint_queues_and_replays_once(site, endpoint):
	"""TC-W3-014 step 2 (URS-W3-011 AC-2): with the endpoint offline the confirmation of
	PO-2026-0002 stays in the durable outbox with reason ENDPOINT_UNAVAILABLE and shows up as
	backlog on the health surface; after recovery `flush_outbox` delivers it exactly once."""
	order = submitted_order(site, SECOND_ORDER, external_ref="GRP-SO-77002")
	book_production(site, order, qty=order.qty)
	endpoint.go_offline()

	complete(site, order)

	queued = confirmations(site, message_state=contracts.QUEUED)
	assert len(queued) == 1
	assert queued[0]["reason_code"] == contracts.REASON_ENDPOINT_UNAVAILABLE
	assert endpoint.messages(contracts.CONFIRMATION_OUT) == []
	assert health.metrics()["outbox_depth"] == 1

	endpoint.go_online()
	assert outbound.flush_outbox(contracts.CONFIRMATION_OUT) == {"delivered": 1, "queued": 0}

	assert len(endpoint.messages(contracts.CONFIRMATION_OUT)) == 1, "no duplicate on recovery"
	assert len(confirmations(site)) == 1
	assert confirmations(site)[0]["message_state"] == contracts.DELIVERED
	assert health.metrics()["outbox_depth"] == 0

	assert outbound.flush_outbox(contracts.CONFIRMATION_OUT) == {"delivered": 0, "queued": 0}
	assert len(endpoint.messages(contracts.CONFIRMATION_OUT)) == 1


def test_tc_w3_014_step_2_the_replayed_confirmation_is_fully_audited(site, endpoint):
	"""TC-W3-014 step 2 (URS-W3-011 AC-2, URS-W3-021): the outage and the recovery are both in
	the audit trail — the failed delivery as a refusal, the recovered one as an execution."""
	order = submitted_order(site, SECOND_ORDER, external_ref="GRP-SO-77002")
	book_production(site, order, qty=order.qty)
	endpoint.go_offline()
	complete(site, order)
	endpoint.go_online()
	outbound.flush_outbox(contracts.CONFIRMATION_OUT)

	name = confirmations(site)[0]["name"]
	trail = audit.entries_for("Boundary Message", name)
	outcomes = [entry["outcome"] for entry in trail]
	assert audit.EXECUTED in outcomes
	assert all(entry["logged_by"] and entry["logged_at"] for entry in trail)
	assert trail[-1]["to_state"] == contracts.DELIVERED
	assert any(contracts.REASON_ENDPOINT_UNAVAILABLE in (entry["detail"] or "") for entry in trail)


def test_tc_w3_014_a_confirmation_without_a_batch_is_refused_not_sent(site, endpoint):
	"""TC-W3-014 step 1 (URS-W3-011 AC-1, URS-W3-013 AC-1): the contract requires at least one
	FG batch, so the CONF-OUT-002 rejection fixture is refused by the outbound validation and
	never reaches the endpoint."""
	payload = schema.fixture("conf-out-002-missing-batch.json")

	name = outbound.emit(payload, reference_doctype="Work Order", reference_name=FIRST_ORDER)

	assert site.db.get_value("Boundary Message", name, "message_state") == contracts.REJECTED
	assert site.db.get_value("Boundary Message", name, "reason_code") == contracts.REASON_CONTRACT_VIOLATION
	assert endpoint.messages(contracts.CONFIRMATION_OUT) == []
