"""TC-W2-001 / TC-W2-002 — genealogy links as system-of-record (W2-1).

Verifies **URS-W2-001 AC-1…3** of `docs/urs/URS-W2-traceability-quality.md`: the links are
written by the posting path itself, a cancel-and-repost corrects them in the same
transaction, and non-batch-managed material produces no link and no incompleteness flag.
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import (
	BATCH_A1,
	BATCH_A2,
	RAW_ITEM,
	RM_WAREHOUSE,
	new_work_order,
	post_consumption,
	post_output,
	require_fixture,
	require_w2_schema,
)

frappe = pytest.importorskip("frappe")
links = pytest.importorskip("rheinwerk_mes.genealogy.links")

PRODUCED = "BATCH-C-9001"


@pytest.fixture
def order(site):
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A1)
	require_fixture(site, "Batch", BATCH_A2)
	return new_work_order(site)


def _links(batch: str, direction: str | None = None) -> list[dict]:
	return links.links_of(batch, direction)


def test_links_written_at_output_recording(site, order):
	"""URS-W2-001 AC-1 / TC-W2-001 steps 1-4 — two consumed links plus one produced link."""
	post_consumption(site, order, [(RAW_ITEM, BATCH_A1, 8.0)])
	post_consumption(site, order, [(RAW_ITEM, BATCH_A2, 2.0)])
	post_output(site, order, PRODUCED, 10.0)

	consumed = {row["batch"]: row["qty"] for row in _links(PRODUCED, links.CONSUMED)}
	produced = _links(PRODUCED, links.PRODUCED)

	assert consumed == {BATCH_A1: 8.0, BATCH_A2: 2.0}, "quantities are recorded exactly"
	assert [(row["batch"], row["qty"]) for row in produced] == [(PRODUCED, 10.0)]
	assert {row["production_order"] for row in _links(PRODUCED)} == {order}
	assert site.db.get_value("Batch", PRODUCED, "qa_state") == "Quarantined"


def test_cancel_and_repost_corrects_the_link_in_the_same_transaction(site, order):
	"""URS-W2-001 AC-2 / TC-W2-002 steps 1-2 — corrected qty replaces the stale link."""
	consumption = post_consumption(site, order, [(RAW_ITEM, BATCH_A2, 2.0)])
	post_output(site, order, PRODUCED, 10.0)
	assert _links(PRODUCED, links.CONSUMED)[0]["qty"] == 2.0

	consumption.cancel()
	post_consumption(site, order, [(RAW_ITEM, BATCH_A2, 3.0)])

	consumed = {row["batch"]: row["qty"] for row in _links(PRODUCED, links.CONSUMED)}
	assert consumed == {BATCH_A2: 3.0}, "the cancelled quantity leaves no stale row"
	assert links.reconcile_work_order(order) == [], "links and stock ledger agree row for row"


def test_non_batch_material_produces_no_link_and_no_incompleteness(site, order):
	"""URS-W2-001 AC-3 / TC-W2-002 step 3 — process water carries no batch, so no link."""
	water = "RW-CHM-9001"
	if not site.db.exists("Item", water):
		site.get_doc(
			{
				"doctype": "Item",
				"item_code": water,
				"item_name": "Prozesswasser",
				"item_group": "Raw Material",
				"stock_uom": "Kg",
				"is_stock_item": 1,
				"has_batch_no": 0,
			}
		).insert(ignore_permissions=True)
	site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": "Rheinwerk Chemie GmbH",
			"set_posting_time": 1,
			"posting_date": "2026-04-01",
			"items": [
				{
					"item_code": water,
					"qty": 50.0,
					"t_warehouse": RM_WAREHOUSE,
					"uom": "Kg",
					"basic_rate": 0.1,
				}
			],
		}
	).insert(ignore_permissions=True).submit()

	post_consumption(site, order, [(RAW_ITEM, BATCH_A1, 5.0), (water, None, 20.0)])
	post_output(site, order, PRODUCED, 10.0)

	assert {row["batch"] for row in _links(PRODUCED, links.CONSUMED)} == {BATCH_A1}
	assert water not in {row["item"] for row in _links(PRODUCED)}
	assert links.is_incomplete(PRODUCED) is False, "an unbatched input does not break the trace"
