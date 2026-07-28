"""TC-W3-015 — GL postings out with the group-ERP account map and the unmapped hold queue.

Verifies **URS-W3-012**: a posted perpetual-inventory movement into the mapped warehouse
FG Lager Süd (500 kg at 4,20 €/kg) emits one schema-valid boundary posting with a balanced
2.100,00 € debit/credit pair on the mapped group-ERP accounts (AC-1); a movement on the
deliberately unmapped RM Lager Nord is held with reason UNMAPPED_WAREHOUSE, alerts naming the
warehouse and the missing map entry, and emits nothing at all (AC-2).

The stock-ledger hook (`hooks.py` → `Stock Entry.on_submit`) is what triggers both, so the
substrate's own posting path is exercised — nothing is called by hand.
"""

from __future__ import annotations

import pytest
from test_w3_boundary_support import (
	FG_WAREHOUSE,
	ITEM,
	QUANTITY,
	RM_WAREHOUSE,
	clear_messages,
	loopback,
	messages,
)

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
contracts = pytest.importorskip("rheinwerk_mes.integration.boundary.contracts")
gl = pytest.importorskip("rheinwerk_mes.integration.boundary.gl")
health = pytest.importorskip("rheinwerk_mes.integration.boundary.health")
schema = pytest.importorskip("rheinwerk_mes.integration.boundary.schema")

COMPANY = "Rheinwerk Chemie GmbH"
RATE = 4.20
RAW_ITEM = "RW-CHM-0001"
POSTING_DATE = "2026-03-12"
EXPECTED_TOTAL = 2100.00


@pytest.fixture
def endpoint(site, monkeypatch):
	clear_messages(site)
	return loopback(monkeypatch)


def receipt(site, item: str, warehouse: str, qty: float, rate: float):
	"""Post a Material Receipt — the shortest real perpetual-inventory posting."""
	entry = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"posting_date": POSTING_DATE,
			"posting_time": "15:00:00",
			"set_posting_time": 1,
			"items": [
				{
					"item_code": item,
					"t_warehouse": warehouse,
					"qty": qty,
					"uom": "Kg",
					"stock_uom": "Kg",
					"conversion_factor": 1,
					"basic_rate": rate,
				}
			],
		}
	)
	entry.flags.ignore_permissions = True
	entry.insert(ignore_permissions=True)
	entry.submit()
	return entry


def postings(site, **filters):
	return messages(site, contracts.GL_POSTING_OUT, **filters)


def test_tc_w3_015_step_1_a_mapped_warehouse_emits_the_balanced_pair(site, endpoint):
	"""TC-W3-015 step 1 (URS-W3-012 AC-1): posting 500 kg at 4,20 €/kg into the mapped
	FG Lager Süd emits one schema-valid GL message whose debit and credit are both exactly
	2.100,00 € on the group-ERP accounts of the map entry."""
	mapping = gl.account_map(FG_WAREHOUSE)
	if mapping is None:
		pytest.skip("group-ERP account map not seeded on this site")

	entry = receipt(site, ITEM, FG_WAREHOUSE, QUANTITY, RATE)

	stored = postings(site)
	assert len(stored) == 1
	assert stored[0]["message_state"] == contracts.DELIVERED
	assert stored[0]["warehouse"] == FG_WAREHOUSE

	sent = endpoint.messages(contracts.GL_POSTING_OUT)
	assert len(sent) == 1
	payload = sent[0]
	assert schema.validate_message(payload) is payload
	assert payload["voucher"]["name"] == entry.name
	assert payload["currency"] == mapping["currency"]
	assert payload["quantity"] == QUANTITY
	assert payload["uom"] == "Kg"

	debit, credit = payload["lines"]
	assert debit["account"] == mapping["stock_account_code"]
	assert credit["account"] == mapping["offset_account_code"]
	assert debit["debit"] == EXPECTED_TOTAL and debit["credit"] == 0.0
	assert credit["credit"] == EXPECTED_TOTAL and credit["debit"] == 0.0
	assert sum(line["debit"] for line in payload["lines"]) == sum(
		line["credit"] for line in payload["lines"]
	), "the emitted pair balances"

	trail = audit.entries_for("Boundary Message", stored[0]["name"])
	assert trail[-1]["outcome"] == audit.EXECUTED


def test_tc_w3_015_step_1_a_redelivered_posting_is_not_emitted_twice(site, endpoint):
	"""TC-W3-015 step 1 (URS-W3-012 AC-1, URS-W3-013 AC-3): the stock ledger entry is the
	once-only key, so re-running the emission for the same voucher delivers nothing new."""
	if gl.account_map(FG_WAREHOUSE) is None:
		pytest.skip("group-ERP account map not seeded on this site")
	entry = receipt(site, ITEM, FG_WAREHOUSE, QUANTITY, RATE)

	again = gl.emit_for_voucher("Stock Entry", entry.name)

	assert len(again["emitted"]) == 1, "same message name, not a second message"
	assert len(postings(site)) == 1
	assert len({message["message_id"] for message in endpoint.messages(contracts.GL_POSTING_OUT)}) == 1


def test_tc_w3_015_step_2_an_unmapped_warehouse_holds_and_emits_nothing(site, endpoint):
	"""TC-W3-015 step 2 (URS-W3-012 AC-2): RM Lager Nord has no map entry, so its posting is
	held with reason UNMAPPED_WAREHOUSE, the reason names the warehouse and the missing map
	DocType, the hold shows on the health surface — and the transport is never reached."""
	assert gl.account_map(RM_WAREHOUSE) is None, "RM Lager Nord stays unmapped by design"

	receipt(site, RAW_ITEM, RM_WAREHOUSE, 100, 2.50)

	held = postings(site, message_state=contracts.HELD)
	assert len(held) == 1
	assert held[0]["reason_code"] == contracts.REASON_UNMAPPED_WAREHOUSE
	assert RM_WAREHOUSE in held[0]["reason"]
	assert contracts.ACCOUNT_MAP_DOCTYPE in held[0]["reason"]

	assert endpoint.messages(contracts.GL_POSTING_OUT) == [], "nothing wrong is emitted"
	assert health.metrics()["hold_queue_depth"] == 1

	trail = audit.entries_for("Boundary Message", held[0]["name"])
	assert trail[-1]["outcome"] == audit.REFUSED
	assert contracts.REASON_UNMAPPED_WAREHOUSE in (trail[-1]["detail"] or "")


def test_tc_w3_015_step_2_a_held_posting_is_refused_by_the_contract_schema(site, endpoint):
	"""TC-W3-015 step 2 (URS-W3-012 AC-2, URS-W3-013 AC-1): the withheld payload is stored as
	evidence and is *not* schema-valid — empty account codes are refused by the frozen
	contract, which is the machine-checkable proof a wrong posting cannot leave the MES."""
	receipt(site, RAW_ITEM, RM_WAREHOUSE, 100, 2.50)
	held = postings(site, message_state=contracts.HELD)[0]

	from rheinwerk_mes.integration.boundary import queues

	payload = queues.payload_of(held["name"])
	assert [line["account"] for line in payload["lines"]] == ["", ""]
	with pytest.raises(schema.SchemaViolation):
		schema.validate_message(payload)


def test_tc_w3_015_step_2_mapping_the_warehouse_releases_the_held_posting(site, endpoint):
	"""TC-W3-015 step 2 (URS-W3-012 AC-2): once the missing map entry exists, the held posting
	is released onto the mapped accounts — the hold is a queue, not a dead letter."""
	receipt(site, RAW_ITEM, RM_WAREHOUSE, 100, 2.50)
	assert len(postings(site, message_state=contracts.HELD)) == 1

	site.get_doc(
		{
			"doctype": contracts.ACCOUNT_MAP_DOCTYPE,
			"warehouse": RM_WAREHOUSE,
			"company": COMPANY,
			"currency": "EUR",
			"stock_account_code": "1300-ROHSTOFFE",
			"offset_account_code": "5900-BESTANDSVERAENDERUNG",
		}
	).insert(ignore_permissions=True)

	assert gl.release_held(RM_WAREHOUSE) == {"released": 1, "held": 0}

	sent = endpoint.messages(contracts.GL_POSTING_OUT)
	assert len(sent) == 1
	assert [line["account"] for line in sent[0]["lines"]] == [
		"1300-ROHSTOFFE",
		"5900-BESTANDSVERAENDERUNG",
	]
	assert postings(site)[0]["message_state"] == contracts.DELIVERED
	assert health.metrics()["hold_queue_depth"] == 0


def test_tc_w3_015_an_issue_from_a_mapped_warehouse_reverses_the_pair(site, endpoint):
	"""TC-W3-015 step 1 (URS-W3-012 AC-1): the direction of the value movement decides the
	side — an outbound movement credits the stock account and debits the offset."""
	if gl.account_map(FG_WAREHOUSE) is None:
		pytest.skip("group-ERP account map not seeded on this site")
	receipt(site, ITEM, FG_WAREHOUSE, QUANTITY, RATE)
	endpoint.reset()

	issue = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": COMPANY,
			"posting_date": POSTING_DATE,
			"posting_time": "16:00:00",
			"set_posting_time": 1,
			"items": [
				{
					"item_code": ITEM,
					"s_warehouse": FG_WAREHOUSE,
					"qty": 10,
					"uom": "Kg",
					"stock_uom": "Kg",
					"conversion_factor": 1,
				}
			],
		}
	)
	issue.flags.ignore_permissions = True
	issue.insert(ignore_permissions=True)
	issue.submit()

	sent = endpoint.messages(contracts.GL_POSTING_OUT)
	assert len(sent) == 1
	stock_line, offset_line = sent[0]["lines"]
	assert stock_line["credit"] > 0 and stock_line["debit"] == 0.0
	assert offset_line["debit"] == stock_line["credit"]
	assert sent[0]["quantity"] < 0
