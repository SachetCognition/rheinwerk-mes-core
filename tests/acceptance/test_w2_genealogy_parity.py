"""TC-W2-040 / TC-W2-041 — characterisation parity for expiry, blocked use and link shape.

Section 4 of `docs/test/TST-W2-traceability-quality.md`:

* **TC-W2-040** (URS-W2-008, Adopt) — ERPNext
  `erpnext/stock/stock_ledger.py` / `erpnext/stock/doctype/batch/batch.py` refuse a
  consumption only once the expiry date lies *before* the posting date; the boundary day
  itself is still issuable. The three boundary fixtures (expiry = posting − 1 / = posting /
  = posting + 1) must produce the identical accept/throw decisions in the estate.
* **TC-W2-041** (URS-W2-011, URS-W2-001, Absorb) — Qcadoo
  `mes-plugins/mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/
  advancedGenealogy/listeners/BatchBasicStateListenerService.java` (a BLOCKED batch is
  unusable) and `.../constants/TrackingRecordFields.java:31-49` (one produced batch, n used
  batches with quantity). The deliberate deviation — advisory propagation to downstream
  batches (URS-W2-009) — has no legacy counterpart and is asserted here as *new* behaviour.

The expiry leg is offline (the contract entrypoint is a pure function); the blocked-use and
link-shape legs need the seeded site.
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import (
	BATCH_A1,
	BATCH_A2,
	BATCH_C1,
	require_fixture,
	require_w2_schema,
	set_state,
)

frappe = pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.execution_gating.contracts")

POSTING_DATE = "01.07.2026"

#: Plant C (ERPNext substrate) baseline decisions — `allowed` on the boundary day itself.
EXPIRY_BOUNDARY_BASELINE = (
	("expiry-minus-one", "30.06.2026", False),
	("expiry-on-posting-date", "01.07.2026", True),
	("expiry-plus-one", "02.07.2026", True),
)

#: Qcadoo baseline decisions for consuming a batch by its state.
BLOCKED_USE_BASELINE = (
	("Released", True),
	("Blocked", False),
)


@pytest.mark.parametrize(("case_id", "expiry", "allowed"), EXPIRY_BOUNDARY_BASELINE)
def test_expiry_boundary_decisions_match_the_substrate_baseline(case_id, expiry, allowed):
	"""URS-W2-008 / TC-W2-040 — identical accept/throw decisions on the date boundary."""
	verdict = contracts.evaluate_expired_issue(
		{
			"batch": BATCH_A1,
			"expiration_date": expiry,
			"posting_date": POSTING_DATE,
			"quantity": 10,
		}
	)

	assert verdict.allowed is allowed, f"{case_id} diverges from the Plant C baseline"
	assert verdict.errors == (() if allowed else (contracts.BATCH_EXPIRED,))


@pytest.mark.parametrize(("state", "usable"), BLOCKED_USE_BASELINE)
def test_blocked_use_decisions_match_the_qcadoo_baseline(site, state, usable):
	"""URS-W2-011 / TC-W2-041 — a BLOCKED batch is unusable, a tracked one is usable.

	Qcadoo baseline: `BatchBasicStateListenerService` refuses use of a blocked batch and
	permits it once the batch is tracked again (`BatchState.java:31-44`).
	"""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A2)
	blocking = pytest.importorskip("rheinwerk_mes.genealogy.blocking")
	set_state(site, BATCH_A2, state)

	assert blocking.is_pickable(BATCH_A2) is usable

	movement = frappe._dict(
		items=[
			frappe._dict(
				item_code="RW-CHM-0001",
				qty=1.0,
				s_warehouse="RM Lager Nord - RWC",
				batch_no=BATCH_A2,
			)
		]
	)
	if usable:
		blocking.enforce_blocked_batch_consumption(movement)
	else:
		with pytest.raises(frappe.ValidationError, match=blocking.RULE_BLOCKED_CONSUMPTION):
			blocking.enforce_blocked_batch_consumption(movement)


def test_link_shape_matches_the_tracking_record_baseline(site):
	"""URS-W2-001 / TC-W2-041 — one produced link, n consumed links carrying quantities.

	`TrackingRecordFields.java:31-49` pins the Qcadoo tracking-record shape: exactly one
	`producedBatch` and a `usedBatchesSimple` collection of (batch, quantity) rows.
	"""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	links = pytest.importorskip("rheinwerk_mes.genealogy.links")
	recorded = links.links_of(BATCH_C1)
	if not recorded:
		pytest.skip("genealogy fixture not seeded on this site")

	produced = [row for row in recorded if row["direction"] == links.PRODUCED]
	consumed = [row for row in recorded if row["direction"] == links.CONSUMED]

	assert len(produced) == 1 and produced[0]["batch"] == BATCH_C1
	assert len(consumed) >= 1
	assert all(row["qty"] > 0 and row["batch"] for row in consumed)
	assert {row["production_order"] for row in recorded} == {produced[0]["production_order"]}


def test_propagation_is_the_documented_deviation_without_legacy_counterpart(site):
	"""URS-W2-009 / TC-W2-041 — the advisory deviation is asserted as *new* behaviour.

	Qcadoo blocks a single batch and stops there; the estate additionally flags every
	downstream batch. Signed off in URS-W2-009; recorded here so the deviation is measured
	rather than assumed.
	"""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A2)
	trace = pytest.importorskip("rheinwerk_mes.genealogy.trace")
	qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
	if not trace.descendants(BATCH_A2):
		pytest.skip("genealogy fixture not seeded on this site")

	set_state(site, BATCH_A2, qa_state.RELEASED)
	qa_state.transition(BATCH_A2, qa_state.BLOCKED, reason="Parität: Sperrung")

	downstream = trace.descendants(BATCH_A2)
	assert all(trace.blocked_ancestors(batch) == [BATCH_A2] for batch in downstream)
	assert all(qa_state.current_state(batch) != qa_state.BLOCKED for batch in downstream), (
		"the deviation is advisory only — downstream dispositions stay with quality"
	)
