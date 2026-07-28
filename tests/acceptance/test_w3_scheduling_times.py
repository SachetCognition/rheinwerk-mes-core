"""TC-W3-008 / TC-W3-009 — TJ/TPZ realization times, minute-exact.

Verifies **URS-W3-006** (realization times from the TJ unit-production and TPZ setup norms
per operation and work centre, parity to the minute) through **TC-W3-008** and the
legacy-parity case **TC-W3-009** of `docs/test/TST-W3-planning-boundary.md`.

URS-W3-006 AC-1: MIX = 30 + 500 × 0,6 = 330 min, FILL = 15 + 500 × 0,3 = 165 min,
order total 495 min on the sequential routing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from test_w3_scheduling_support import (
	FILL_MINUTES,
	FILL_WORK_CENTRE,
	FIRST_ORDER,
	MIX_MINUTES,
	MIX_WORK_CENTRE,
	ORDER_MINUTES,
	accepted_order,
	draft_schedule,
	entry_for,
	operation_for,
	require_norms,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "tests"):
	if str(path) not in sys.path:
		sys.path.insert(0, str(path))

from characterisation.registry import get as get_contract  # noqa: E402

realization_time = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.realization_time")
frappe = pytest.importorskip("frappe")
lifecycle = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.lifecycle")


def test_operation_duration_is_setup_plus_unit_time():
	"""URS-W3-006 AC-1 / TC-W3-008 step 1 — the two seeded norms, computed offline."""
	assert realization_time.operation_duration(500, 0.6, 30) == MIX_MINUTES
	assert realization_time.operation_duration(500, 0.3, 15) == FILL_MINUTES


def test_run_time_is_truncated_not_rounded():
	"""URS-W3-006 AC-1 / TC-W3-008 — whole minutes, truncated like the legacy BigDecimal."""
	assert realization_time.operation_duration(1, 0.6, 30) == 30
	assert realization_time.operation_duration(7, 0.3, 15) == 17
	assert realization_time.operation_duration(500, 0.6, 0) == 300


def test_order_total_is_the_sequential_sum(site):
	"""URS-W3-006 AC-1 / TC-W3-008 step 2 — 330 + 165 = 495 min for PO-2026-0001."""
	require_norms(site)
	accepted_order(site, FIRST_ORDER)
	operations, total = lifecycle.order_realization(FIRST_ORDER)
	assert total == ORDER_MINUTES
	durations = {row.operation: row.duration_min for row in operations}
	assert durations == {"MIX": MIX_MINUTES, "FILL": FILL_MINUTES}


def test_schedule_carries_the_norm_breakdown_per_work_centre(site):
	"""URS-W3-006 AC-2 / TC-W3-008 step 3 — TPZ, TJ and the derived minutes are on the plan."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	assert entry_for(schedule, FIRST_ORDER).realization_min == ORDER_MINUTES

	mix = operation_for(schedule, FIRST_ORDER, "MIX")
	assert (mix.workstation, mix.tpz_min, mix.tj_min_per_unit) == (MIX_WORK_CENTRE, 30, 0.6)
	assert (mix.setup_min, mix.run_min, mix.duration_min) == (30, 300, MIX_MINUTES)

	fill = operation_for(schedule, FIRST_ORDER, "FILL")
	assert (fill.workstation, fill.tpz_min, fill.tj_min_per_unit) == (FILL_WORK_CENTRE, 15, 0.3)
	assert (fill.setup_min, fill.run_min, fill.duration_min) == (15, 60 + 90, FILL_MINUTES)

	# The sequential routing: FILL starts when MIX ends, the order ends 495 min after start.
	assert fill.planned_start == mix.planned_end
	assert (fill.planned_end - mix.planned_start).total_seconds() == ORDER_MINUTES * 60


def test_norms_come_from_the_seeder_not_from_the_test(site):
	"""URS-W3-006 AC-2 / TC-W3-008 — the TJ/TPZ norms are committed fixture master data."""
	require_norms(site)
	mix = site.db.get_value(
		"Operation Time Norm",
		{"operation": "MIX", "workstation": MIX_WORK_CENTRE},
		["tpz_min", "tj_min_per_unit"],
	)
	assert mix == (30.0, 0.6)


def test_legacy_parity_matrix_is_minute_exact():
	"""URS-W3-006 AC-3 / TC-W3-009 — the donor matrix runs against the target (offline)."""
	contract = get_contract("CHAR-REALIZATION-TIME-01")
	assert contract.legacy_source == "OrderRealizationTimeServiceImpl.java:156-186"
	assert contract.resolution().is_target_implementation
	cases = contract.cases()
	assert len(cases) >= 10, "TC-W3-009 requires at least ten TJ/TPZ combinations"
	quantities = {case["inputs"].get("quantity") for case in cases}
	setups = {case["inputs"].get("tpz_min") for case in cases}
	assert 1 in quantities, "the quantity = 1 edge case is missing"
	assert 0 in setups, "the TPZ = 0 edge case is missing"
	for case in cases:
		contract.check(case)
