"""TC-W3-013 — orders in: happy path, duplicate, rejection.

Verifies **URS-W3-010**: playing contract fixture ERP-IN-001 creates the sales input keyed by
GRP-SO-77001 and available to Production Plan creation (AC-1); replaying it creates no second
demand and logs a duplicate naming GRP-SO-77001 (AC-2); playing ERP-IN-002 (unknown item)
rejects into the error queue with a machine-readable reason and leaves no partial write (AC-3).

Every processed, duplicated and rejected message writes the W1 gate audit (URS-W3-021).
"""

from __future__ import annotations

import pytest
from test_w3_boundary_support import ITEM, clear_messages, messages

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
contracts = pytest.importorskip("rheinwerk_mes.integration.boundary.contracts")
inbound = pytest.importorskip("rheinwerk_mes.integration.boundary.inbound")
schema = pytest.importorskip("rheinwerk_mes.integration.boundary.schema")

HAPPY = "erp-in-001-happy.json"
DUPLICATE = "erp-in-001-duplicate.json"
UNKNOWN_ITEM = "erp-in-002-unknown-item.json"
MASTER_ORDER = "erp-in-003-master-order.json"


@pytest.fixture
def clean_boundary(site):
	"""Start from an empty message store; the `site` fixture rolls the deletion back."""
	clear_messages(site)
	site.db.delete("ERP Sales Input")
	yield site


def test_tc_w3_013_step_1_playing_erp_in_001_creates_the_sales_input(clean_boundary):
	"""TC-W3-013 step 1 (URS-W3-010 AC-1): playing ERP-IN-001 creates a sales-input record
	referencing GRP-SO-77001 with 500 kg RW-CHM-0003 into FG Lager Süd, available to plan
	creation, and the message is stored as processed with an audit entry."""
	site = clean_boundary
	result = inbound.play_fixture(HAPPY)

	assert result.accepted
	assert result.demand == "GRP-SO-77001"

	demand = site.get_doc("ERP Sales Input", "GRP-SO-77001")
	assert demand.item_code == ITEM
	assert demand.quantity == 500.0
	assert demand.uom == "Kg"
	assert demand.warehouse == "FG Lager Süd - RWC"
	assert demand.demand_state == "Offen"
	assert demand.external_order_kind == "sales-order"

	stored = messages(site, contracts.ORDERS_IN)
	assert len(stored) == 1
	assert stored[0]["message_state"] == contracts.PROCESSED
	assert stored[0]["attempts"] == 1

	trail = audit.entries_for("Boundary Message", stored[0]["name"])
	assert trail, "processing a boundary message writes the W1 gate audit (URS-W3-021)"
	assert trail[-1]["outcome"] == audit.EXECUTED


def test_tc_w3_013_step_2_replaying_erp_in_001_creates_no_second_demand(clean_boundary):
	"""TC-W3-013 step 2 (URS-W3-010 AC-2): the redelivered message creates no duplicate
	demand; the duplicate is logged against GRP-SO-77001 and the attempt counted."""
	site = clean_boundary
	inbound.play_fixture(HAPPY)
	before = site.db.get_value("ERP Sales Input", "GRP-SO-77001", "modified")

	result = inbound.play_fixture(DUPLICATE)

	assert result.reason_code == contracts.REASON_DUPLICATE
	assert "GRP-SO-77001" in result.reason
	assert site.db.count("ERP Sales Input", {"external_order_ref": "GRP-SO-77001"}) == 1
	assert site.db.get_value("ERP Sales Input", "GRP-SO-77001", "modified") == before

	stored = messages(site, contracts.ORDERS_IN)
	assert len(stored) == 1, "a redelivery is the same message, not a second one"
	assert stored[0]["attempts"] == 2

	trail = audit.entries_for("Boundary Message", stored[0]["name"])
	assert any(
		entry["outcome"] == audit.REFUSED and contracts.REASON_DUPLICATE in (entry["detail"] or "")
		for entry in trail
	), "the duplicate is audited with its reason code (URS-W3-021)"


def test_tc_w3_013_step_3_unknown_item_is_rejected_without_partial_write(clean_boundary):
	"""TC-W3-013 step 3 (URS-W3-010 AC-3): ERP-IN-002 names an unknown item, so the message
	lands in the error queue with reason code UNKNOWN_ITEM and the JSON path of the offending
	field — and not a single row of its demand is written."""
	site = clean_boundary
	payload = schema.fixture(UNKNOWN_ITEM)

	result = inbound.play_fixture(UNKNOWN_ITEM)

	assert not result.accepted
	assert result.outcome == contracts.REJECTED
	assert result.reason_code == contracts.REASON_UNKNOWN_ITEM
	assert "$.demand.item_code" in result.reason
	assert result.demand is None

	assert not site.db.exists("ERP Sales Input", payload["external_order_ref"])
	assert site.db.count("ERP Sales Input") == 0

	stored = messages(site, contracts.ORDERS_IN, message_state=contracts.REJECTED)
	assert len(stored) == 1
	assert stored[0]["reason_code"] == contracts.REASON_UNKNOWN_ITEM

	trail = audit.entries_for("Boundary Message", stored[0]["name"])
	assert trail[-1]["outcome"] == audit.REFUSED
	assert contracts.REASON_UNKNOWN_ITEM in (trail[-1]["detail"] or "")


def test_tc_w3_013_a_contract_violation_is_rejected_with_the_same_discipline(clean_boundary):
	"""TC-W3-013 (URS-W3-010 AC-3, URS-W3-013 AC-1): a message that violates the frozen schema
	is refused before any master-data lookup, with the CONTRACT_VIOLATION reason code."""
	site = clean_boundary
	payload = schema.fixture(HAPPY)
	broken = {**payload, "message_id": "ERP-IN-777", "demand": {**payload["demand"]}}
	del broken["demand"]["required_by"]

	result = inbound.process(broken)

	assert result.reason_code == contracts.REASON_CONTRACT_VIOLATION
	assert "required_by" in result.reason
	assert site.db.count("ERP Sales Input") == 0


def test_tc_w3_013_a_corrected_message_is_reprocessed_on_redelivery(clean_boundary):
	"""TC-W3-013 step 3 (URS-W3-010 AC-2/AC-3): only an *accepted* message is a duplicate — a
	rejected one is retried on redelivery, so correcting the master data and resending works."""
	site = clean_boundary
	payload = schema.fixture(UNKNOWN_ITEM)
	assert inbound.process(payload).outcome == contracts.REJECTED

	corrected = {**payload, "demand": {**payload["demand"], "item_code": ITEM}}
	result = inbound.process(corrected)

	assert result.accepted
	assert site.db.exists("ERP Sales Input", payload["external_order_ref"])
	stored = messages(site, contracts.ORDERS_IN)
	assert len(stored) == 1 and stored[0]["message_state"] == contracts.PROCESSED


def test_tc_w3_013_the_carried_master_order_sync_is_processed_too(clean_boundary):
	"""TC-W3-013 (URS-W3-010 AC-1, URS-W3-019): the second carried orders-in sync from the
	W3-7 register (XS-02, Qcadoo `masterOrder.externalNumber`) is processed by the same
	entrypoint, as a master-order demand."""
	site = clean_boundary
	result = inbound.play_fixture(MASTER_ORDER)

	assert result.accepted
	demand = site.get_doc("ERP Sales Input", result.demand)
	assert demand.external_order_kind == "master-order"
	assert demand.quantity == 1200.0


def test_tc_w3_013_an_unknown_partner_reference_is_carried_not_resolved(clean_boundary):
	"""TC-W3-013 (URS-W3-010 AC-1, DEC-W3-020/D5): the group ERP owns partner masters, so the
	MES stores `customer_ref` as an opaque key — an unknown customer is no rejection reason,
	unlike an unknown item."""
	site = clean_boundary
	payload = schema.fixture(HAPPY)
	payload = {**payload, "demand": {**payload["demand"], "customer_ref": "KD-UNBEKANNT-9999"}}

	result = inbound.process(payload)

	assert result.accepted
	demand = site.get_doc("ERP Sales Input", result.demand)
	assert demand.customer_ref == "KD-UNBEKANNT-9999"
	assert not site.db.exists("Customer", "KD-UNBEKANNT-9999"), "the MES must not master partners"
