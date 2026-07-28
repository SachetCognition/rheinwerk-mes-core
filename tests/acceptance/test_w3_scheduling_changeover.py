"""TC-W3-010 — line changeover norms applied when sequencing a line.

Verifies **URS-W3-007** (changeover norms inserted between consecutive orders; a transition
without a matching norm inserts no time and is annotated) through **TC-W3-010** of
`docs/test/TST-W3-planning-boundary.md`.
"""

from __future__ import annotations

import pytest
from test_w3_scheduling_support import (
	CHANGEOVER_MINUTES,
	FIRST_ORDER,
	LINE,
	PLAN_START,
	SECOND_ORDER,
	accepted_order,
	draft_schedule,
	entry_for,
	require_norms,
)

changeover = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.changeover")
frappe = pytest.importorskip("frappe")

PRODUCT = "RW-CHM-0003"
OTHER_PRODUCT = "RW-CHM-0002"


def test_changeover_time_separates_two_orders_on_the_line(site):
	"""URS-W3-007 AC-1 / TC-W3-010 step 1 — the second order starts 45 min after the first."""
	schedule = draft_schedule(site)
	first = entry_for(schedule, FIRST_ORDER)
	second = entry_for(schedule, SECOND_ORDER)
	assert second.changeover_min == CHANGEOVER_MINUTES
	assert second.changeover_note is None
	assert (second.planned_start - first.planned_end).total_seconds() == CHANGEOVER_MINUTES * 60
	assert second.planned_start >= first.planned_end


def test_first_order_of_the_line_carries_no_changeover(site):
	"""URS-W3-007 AC-1 / TC-W3-010 — nothing precedes the first order."""
	schedule = draft_schedule(site)
	assert entry_for(schedule, FIRST_ORDER).changeover_min == 0


def test_missing_norm_inserts_no_time_and_is_annotated(site):
	"""URS-W3-007 AC-2 / TC-W3-010 step 2 — the gap is visible, not silently zero."""
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	require_norms(site)
	for name in (FIRST_ORDER, SECOND_ORDER):
		accepted_order(site, name)
	site.db.delete("Line Changeover Norm", {"production_line": LINE})
	schedule = site.get_doc(
		"Line Schedule",
		lifecycle.create_schedule(LINE, [FIRST_ORDER, SECOND_ORDER], PLAN_START),
	)
	second = entry_for(schedule, SECOND_ORDER)
	assert second.changeover_min == 0
	assert second.changeover_note == changeover.NO_NORM_NOTE
	assert second.planned_start == entry_for(schedule, FIRST_ORDER).planned_end


def test_norm_is_committed_master_data(site):
	"""URS-W3-007 AC-1 / TC-W3-010 — the 45-minute flush comes from the seeder."""
	require_norms(site)
	minutes = site.db.get_value(
		"Line Changeover Norm",
		{"production_line": LINE, "from_item": PRODUCT, "to_item": PRODUCT},
		"changeover_min",
	)
	assert minutes == float(CHANGEOVER_MINUTES)


def test_specific_product_pair_beats_a_broad_norm():
	"""URS-W3-007 AC-1 / TC-W3-010 — legacy precedence: specific pair, then line, then newest."""
	norms = [
		{"production_line": LINE, "from_item": PRODUCT, "to_item": None, "changeover_min": 20, "sequence": 1},
		{
			"production_line": LINE,
			"from_item": PRODUCT,
			"to_item": OTHER_PRODUCT,
			"changeover_min": 35,
			"sequence": 2,
		},
		{
			"production_line": None,
			"from_item": PRODUCT,
			"to_item": OTHER_PRODUCT,
			"changeover_min": 90,
			"sequence": 3,
		},
	]
	minutes, note = changeover.changeover_minutes(norms, PRODUCT, OTHER_PRODUCT, LINE)
	assert (minutes, note) == (35, None)


def test_line_specific_norm_beats_a_line_agnostic_one():
	"""URS-W3-007 AC-1 / TC-W3-010 — a norm of another line is never a candidate."""
	norms = [
		{
			"production_line": None,
			"from_item": PRODUCT,
			"to_item": OTHER_PRODUCT,
			"changeover_min": 90,
			"sequence": 1,
		},
		{
			"production_line": LINE,
			"from_item": PRODUCT,
			"to_item": OTHER_PRODUCT,
			"changeover_min": 30,
			"sequence": 2,
		},
		{
			"production_line": "LINE-2",
			"from_item": PRODUCT,
			"to_item": OTHER_PRODUCT,
			"changeover_min": 5,
			"sequence": 3,
		},
	]
	assert changeover.changeover_minutes(norms, PRODUCT, OTHER_PRODUCT, LINE) == (30, None)
	assert changeover.best_matching(norms, PRODUCT, OTHER_PRODUCT, "LINE-2")["changeover_min"] == 5


def test_no_matching_norm_returns_zero_and_the_note():
	"""URS-W3-007 AC-2 / TC-W3-010 step 2 — the pure calculator's contract."""
	assert changeover.best_matching([], PRODUCT, OTHER_PRODUCT, LINE) is None
	assert changeover.changeover_minutes([], PRODUCT, OTHER_PRODUCT, LINE) == (0, changeover.NO_NORM_NOTE)
