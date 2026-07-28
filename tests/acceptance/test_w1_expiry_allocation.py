"""TC-W1-032 — the expiry hard stop inside automatic allocation (W1-9).

Verifies **URS-W1-030 AC-1** of `docs/urs/URS-W1-production-core.md`: under the signed-off
estate policy (`docs/decisions/DEC-W1-030-expiry-policy.md`) an expired batch is skipped by
the disposal algorithm and the issue is refused when no unexpired stock covers the demand —
it is never silently issued.

The seeded FEFO warehouse RM Lager Nord holds both frozen FEFO fixture resources of
RW-CHM-0001: BATCH-A-0002 (50 kg, expired 30.06.2026) and BATCH-A-0001 (500 kg,
31.12.2026). FEFO would rank the expired batch *first*, which is exactly what makes it the
interesting case; the posting date is passed explicitly (01.07.2026) so the test never
depends on the machine clock.
"""

from __future__ import annotations

import pytest
from test_w1_gating_support import RM_WAREHOUSE, require_fixture

frappe = pytest.importorskip("frappe")
allocation = pytest.importorskip("rheinwerk_mes.execution_gating.allocation")
disposal = pytest.importorskip("rheinwerk_mes.warehouse.disposal")

ITEM = "RW-CHM-0001"
EXPIRED_BATCH = "BATCH-A-0002"
UNEXPIRED_BATCH = "BATCH-A-0001"
POSTING_DATE = "2026-07-01"


@pytest.fixture
def seeded(site):
	require_fixture(site, "Batch", EXPIRED_BATCH)
	require_fixture(site, "Batch", UNEXPIRED_BATCH)
	return site


def test_expired_batch_is_skipped_although_fefo_ranks_it_first(seeded):
	"""URS-W1-030 AC-1 / TC-W1-032 step 1 — demand covered by unexpired stock skips it."""
	assert disposal.warehouse_algorithm(RM_WAREHOUSE) == "FEFO"
	assert disposal.picking_order_for_warehouse(ITEM, RM_WAREHOUSE)[0] == EXPIRED_BATCH, (
		"FEFO must still rank the earliest expiry first — the policy filters, it does not reorder"
	)

	allocated = allocation.allocate_under_expiry_policy(ITEM, RM_WAREHOUSE, 400, POSTING_DATE)

	assert [batch for batch, _qty in allocated] == [UNEXPIRED_BATCH]
	assert sum(qty for _batch, qty in allocated) == 400


def test_issue_is_refused_when_only_expired_stock_could_cover_the_demand(seeded):
	"""URS-W1-030 AC-1 / TC-W1-032 step 2 — refusal, not a partial or silent allocation."""
	before = seeded.db.count("Execution Gate Log")

	with pytest.raises(frappe.ValidationError) as refusal:
		allocation.allocate_under_expiry_policy(ITEM, RM_WAREHOUSE, 520, POSTING_DATE)

	message = str(refusal.value)
	assert "Regel" in message and "Behebung" in message, "refusals are hard-gate modals"
	assert EXPIRED_BATCH in message and "30.06.2026" in message, "the expired batch is named"
	assert seeded.db.count("Execution Gate Log") == before + 1, "the refusal is logged immutably"


def test_expiring_and_expired_stock_carry_signal_states(seeded):
	"""URS-W1-030 design conformance / TC-W1-032 step 2 — red for expired, amber near expiry."""
	view = allocation.allocation_view(ITEM, RM_WAREHOUSE, 520, POSTING_DATE)

	signals = {row["batch"]: row["signal"] for row in view["resources"]}
	assert signals[EXPIRED_BATCH] == allocation.SIGNAL_EXPIRED
	assert view["covered"] is False
	assert view["posting_date"] == "01.07.2026"

	amber = allocation.expiry_signal(frappe.utils.getdate("2026-07-20"), frappe.utils.getdate(POSTING_DATE))
	assert amber == allocation.SIGNAL_EXPIRING, "a batch expiring within 30 days is amber"


def test_stock_entry_auto_allocation_never_picks_the_expired_batch(seeded):
	"""URS-W1-030 AC-1 / TC-W1-032 step 1 — the policy is wired into the posting path.

	A Material Issue row that names no batch is auto-allocated on validate; FEFO would take
	BATCH-A-0002 first, the policy takes the unexpired batch instead.
	"""
	entry = seeded.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": "Rheinwerk Chemie GmbH",
			"posting_date": POSTING_DATE,
			"posting_time": "09:00:00",
			"set_posting_time": 1,
			"items": [{"item_code": ITEM, "qty": 10, "s_warehouse": RM_WAREHOUSE, "uom": "Kg"}],
		}
	)
	entry.flags.ignore_permissions = True
	entry.run_method("validate")

	assert entry.items[0].batch_no == UNEXPIRED_BATCH


def test_unexpired_demand_is_unaffected_by_the_policy(seeded):
	"""URS-W1-030 AC-1 — before the expiry date both batches remain allocatable (control)."""
	allocated = allocation.allocate_under_expiry_policy(ITEM, RM_WAREHOUSE, 520, "2026-06-01")

	assert [batch for batch, _qty in allocated] == [EXPIRED_BATCH, UNEXPIRED_BATCH]
	assert sum(qty for _batch, qty in allocated) == 520
