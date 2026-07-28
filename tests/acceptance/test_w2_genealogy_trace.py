"""TC-W2-003 / TC-W2-006 — multi-level trace browsing and incompleteness (W2-1).

Verifies **URS-W2-002 AC-1…3** (forward/backward arbitrary depth, no cycles, no duplicate
nodes) and **URS-W2-004 AC-1/AC-2** (`genealogy_incomplete` advisory plus the trace-boundary
date) against the seeded chain SUP-K7-0001 → BATCH-A-0002 → {BATCH-C-1001, BATCH-C-1002}.
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import (
	BATCH_A1,
	BATCH_A2,
	BATCH_C1,
	BATCH_C2,
	COMPOUND_ITEM,
	SUPPLIER_BATCH,
	require_fixture,
	require_w2_schema,
)

pytest.importorskip("frappe")
trace = pytest.importorskip("rheinwerk_mes.genealogy.trace")
links = pytest.importorskip("rheinwerk_mes.genealogy.links")
ribbon = pytest.importorskip("rheinwerk_mes.genealogy.ribbon")

ORPHAN = "RB-ORPHAN"


@pytest.fixture
def chain(site):
	require_w2_schema(site)
	for batch in (SUPPLIER_BATCH, BATCH_A1, BATCH_A2, BATCH_C1, BATCH_C2):
		require_fixture(site, "Batch", batch)
	if not links.links_of(BATCH_C1, links.CONSUMED):
		pytest.skip("genealogy fixture not seeded on this site")
	return site


def test_backward_trace_shows_level_one_inputs_with_quantities(chain):
	"""URS-W2-002 AC-1 / TC-W2-003 step 1 — both inputs of BATCH-C-1001 with quantities."""
	tree = trace.backward(BATCH_C1)

	level_one = {node["batch"]: node["qty"] for node in trace.nodes_at_level(tree, 1)}
	assert level_one == {BATCH_A1: 480.0, BATCH_A2: 20.0}
	assert all(node["uom"] == "Kg" for node in trace.nodes_at_level(tree, 1)), "mass in kg"


def test_backward_trace_reaches_the_supplier_lot_without_revisiting_nodes(chain):
	"""URS-W2-002 AC-1/AC-3 / TC-W2-003 step 2 — level 2 adds SUP-K7-0001, once."""
	nodes = trace.flatten(trace.backward(BATCH_C1))

	assert [node["batch"] for node in nodes if node["level"] == 2] == [SUPPLIER_BATCH]
	visited = [node["batch"] for node in nodes]
	assert len(visited) == len(set(visited)), "no node is visited twice"


def test_forward_trace_lists_both_consumers_with_their_production_orders(chain):
	"""URS-W2-002 AC-2 / TC-W2-003 step 3 — BATCH-A-0002 feeds both FG batches."""
	nodes = trace.nodes_at_level(trace.forward(BATCH_A2), 1)

	consumers = {node["batch"]: node["production_order"] for node in nodes}
	assert set(consumers) == {BATCH_C1, BATCH_C2}
	assert all(order for order in consumers.values()), "each edge names its production order"
	assert set(trace.descendants(SUPPLIER_BATCH)) == {BATCH_A2, BATCH_C1, BATCH_C2}


def test_incomplete_genealogy_is_flagged_and_rendered_with_an_advisory_pill(chain):
	"""URS-W2-004 AC-1/AC-2 / TC-W2-006 steps 1-3 — flag, pill and boundary date."""
	chain.get_doc(
		{
			"doctype": "Batch",
			"batch_id": ORPHAN,
			"item": COMPOUND_ITEM,
			"manufacturing_date": "2026-01-02",
			"expiry_date": "2027-01-02",
		}
	).insert(ignore_permissions=True)
	links.mark_incomplete(ORPHAN, trace_boundary_date="2026-01-01")

	node = trace.backward(ORPHAN)
	assert links.is_incomplete(ORPHAN) is True
	assert node["genealogy_incomplete"] is True
	assert node["trace_boundary_date"] == "01.01.2026", "German date format on the boundary"

	pills = ribbon.ribbon(ORPHAN)["focus"]["pills"]
	advisory = [pill for pill in pills if pill["state"] == "genealogy_incomplete"]
	assert advisory, "the trace does not terminate silently — it carries an advisory"
	assert advisory[0]["tone"] == "amber" and advisory[0]["icon"], "icon + label + colour"
	assert "01.01.2026" in advisory[0]["label"]
