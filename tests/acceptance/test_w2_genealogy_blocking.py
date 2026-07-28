"""TC-W2-013 … TC-W2-017 — blocking, picking exclusion and quarantine (W2-3).

Verifies **URS-W2-009 AC-1…3** (advisory propagation through the genealogy and its
clearance), **URS-W2-010 AC-1…3** (Blocked/Quarantined stock excluded from proposals and
reservations, terminal scan refused with a logged modal), **URS-W2-011 AC-1/AC-2**
(consumption refused in the UI-facing logic and in the server hook, no link written) and
**URS-W2-012 AC-1/AC-2** (quarantine putaway plus the role gate on leaving quarantine).
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import (
	ADDITIVE_ITEM,
	BATCH_A1,
	BATCH_A2,
	BATCH_C1,
	BATCH_C2,
	COMPOUND_ITEM,
	FG_WAREHOUSE,
	QUARANTINE_LOCATION,
	RAW_ITEM,
	RM_WAREHOUSE,
	SUPPLIER_BATCH,
	new_work_order,
	post_consumption,
	require_fixture,
	require_w2_schema,
	set_state,
)

frappe = pytest.importorskip("frappe")
blocking = pytest.importorskip("rheinwerk_mes.genealogy.blocking")
quarantine = pytest.importorskip("rheinwerk_mes.genealogy.quarantine")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
trace = pytest.importorskip("rheinwerk_mes.genealogy.trace")
links = pytest.importorskip("rheinwerk_mes.genealogy.links")
availability = pytest.importorskip("rheinwerk_mes.warehouse.availability")
disposal = pytest.importorskip("rheinwerk_mes.warehouse.disposal")

OPERATOR = "o.weber@rheinwerk-chemie.example"
CLERK = "w.braun@rheinwerk-chemie.example"
HANDLING_UNIT = "HU-000123"


@pytest.fixture
def chain(site):
	require_w2_schema(site)
	for batch in (BATCH_A2, BATCH_C1, BATCH_C2):
		require_fixture(site, "Batch", batch)
	if not links.consumers_of(BATCH_A2):
		pytest.skip("genealogy fixture not seeded on this site")
	set_state(site, BATCH_A2, qa_state.RELEASED)
	yield site
	site.set_user("Administrator")


def test_blocking_propagates_advisories_and_leaves_downstream_states_untouched(chain):
	"""URS-W2-009 AC-1/AC-3 / TC-W2-013 steps 1-2 — advisories at every level, amber pill."""
	before = {batch: qa_state.current_state(batch) for batch in (BATCH_C1, BATCH_C2)}

	qa_state.transition(BATCH_A2, qa_state.BLOCKED, reason="Lieferantenrückruf K7/2026-06")

	assert trace.blocked_ancestors(BATCH_C1) == [BATCH_A2]
	assert trace.blocked_ancestors(BATCH_C2) == [BATCH_A2]
	assert {batch: qa_state.current_state(batch) for batch in (BATCH_C1, BATCH_C2)} == before

	pill = blocking.advisory_pill(BATCH_C1)
	assert pill["tone"] == "amber" and pill["icon"] and BATCH_A2 in pill["label"]


def test_unblocking_clears_advisories_only_when_no_blocked_ancestor_remains(chain):
	"""URS-W2-009 AC-2 / TC-W2-013 step 3 — a second blocked ancestor keeps its advisory."""
	set_state(chain, SUPPLIER_BATCH, qa_state.RELEASED)
	qa_state.transition(BATCH_A2, qa_state.BLOCKED, reason="Rückruf")
	qa_state.transition(SUPPLIER_BATCH, qa_state.BLOCKED, reason="Lieferantenbefund")
	assert set(trace.blocked_ancestors(BATCH_C1)) == {BATCH_A2, SUPPLIER_BATCH}

	qa_state.transition(SUPPLIER_BATCH, qa_state.RELEASED, reason="Nachprüfung bestanden")
	assert trace.blocked_ancestors(BATCH_C1) == [BATCH_A2], "the other ancestor stays flagged"

	qa_state.transition(BATCH_A2, qa_state.RELEASED, reason="Freigabe nach Nachprüfung")
	assert trace.blocked_ancestors(BATCH_C1) == []


def test_blocked_and_quarantined_stock_is_excluded_from_picking_and_reservation(chain):
	"""URS-W2-010 AC-1/AC-2 / TC-W2-014 steps 1-2 — one predicate, both surfaces."""
	set_state(chain, BATCH_A2, qa_state.BLOCKED)
	set_state(chain, BATCH_C1, qa_state.QUARANTINED)

	proposal = disposal.picking_order_for_warehouse(RAW_ITEM, RM_WAREHOUSE)
	assert BATCH_A2 not in proposal and BATCH_A1 in proposal
	assert blocking.is_pickable(BATCH_A2) is False
	assert blocking.pickable_batches([BATCH_A1, BATCH_A2]) == [BATCH_A1]

	on_hand = availability.ledger_balance(COMPOUND_ITEM, FG_WAREHOUSE)
	available = availability.available_qty(COMPOUND_ITEM, FG_WAREHOUSE)
	assert blocking.excluded_qty(COMPOUND_ITEM, FG_WAREHOUSE) > 0
	assert available < on_hand, "quarantined quantity is not reservable"


def test_terminal_scan_of_blocked_stock_is_refused_and_logged(chain):
	"""URS-W2-010 AC-3 / TC-W2-015 steps 1-2 — modal names rule, record and resolution."""
	set_state(chain, BATCH_A2, qa_state.BLOCKED)
	before = chain.db.count("Execution Gate Log")

	with pytest.raises(frappe.ValidationError) as refusal:
		blocking.assert_pickable(BATCH_A2, handling_unit=HANDLING_UNIT)

	message = str(refusal.value)
	assert blocking.RULE_BLOCKED_PICKING in message, "the rule identifier is named"
	assert BATCH_A2 in message and HANDLING_UNIT in message, "the record is named"
	assert "Behebung" in message, "the resolution is named"
	assert chain.db.count("Execution Gate Log") == before + 1, "the refusal is audited"


def test_blocked_batch_consumption_is_refused_by_the_server_hook(chain):
	"""URS-W2-011 AC-1/AC-2 / TC-W2-016 steps 1-2 — same rule in UI logic and API path."""
	set_state(chain, BATCH_A2, qa_state.BLOCKED)
	order = new_work_order(chain)
	before = chain.db.count("Execution Gate Log")

	with pytest.raises(frappe.ValidationError) as refusal:
		post_consumption(chain, order, [(RAW_ITEM, BATCH_A2, 2.0)])

	message = str(refusal.value)
	assert blocking.RULE_BLOCKED_CONSUMPTION in message
	assert BATCH_A2 in message and "Behebung" in message
	assert chain.db.count("Execution Gate Log") > before, "the refusal is audited"
	assert links.rebuild_links_for_work_order(order) == [], "no genealogy link was written"


def test_quarantine_putaway_and_the_role_gate_on_leaving_quarantine(chain):
	"""URS-W2-012 AC-1/AC-2 / TC-W2-017 steps 1-3 — putaway, refusal, clerk posts."""
	if not chain.db.exists("Storage Location", QUARANTINE_LOCATION):
		pytest.skip("quarantine location fixture not seeded on this site")
	set_state(chain, BATCH_A2, qa_state.QUARANTINED)

	assert quarantine.is_quarantine_location(QUARANTINE_LOCATION) is True
	assert quarantine.putaway_proposal(BATCH_A2, RM_WAREHOUSE) == QUARANTINE_LOCATION

	movement = frappe._dict(
		items=[
			frappe._dict(
				item_code=RAW_ITEM,
				qty=1.0,
				s_warehouse=RM_WAREHOUSE,
				storage_location=QUARANTINE_LOCATION,
				batch_no=BATCH_A2,
			)
		]
	)
	with pytest.raises(frappe.ValidationError) as refusal:
		quarantine.enforce_quarantine_exit(movement)
	assert quarantine.RULE_QUARANTINE_EXIT in str(refusal.value)

	set_state(chain, BATCH_A2, qa_state.RELEASED)
	if chain.db.exists("User", OPERATOR):
		chain.set_user(OPERATOR)
		with pytest.raises(frappe.PermissionError):
			quarantine.enforce_quarantine_exit(movement)
		chain.set_user("Administrator")

	if chain.db.exists("User", CLERK):
		chain.get_doc("User", CLERK).add_roles("Rheinwerk Warehouse Clerk")
		chain.set_user(CLERK)
	quarantine.enforce_quarantine_exit(movement)  # released stock, permitted role → posts


def test_additive_stock_of_a_blocked_batch_is_absent_from_its_proposal(chain):
	"""URS-W2-010 AC-1 / TC-W2-014 step 1 — the sole-stock case names no candidate."""
	set_state(chain, SUPPLIER_BATCH, qa_state.BLOCKED)

	proposal = disposal.picking_order_for_warehouse(ADDITIVE_ITEM, RM_WAREHOUSE)

	assert SUPPLIER_BATCH not in proposal
