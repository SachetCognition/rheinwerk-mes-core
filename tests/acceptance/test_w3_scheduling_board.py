"""Schedule board — German-first, dense, virtualized (URS-W3-005, URS-W3-020).

Supporting suite for **TC-W3-006** (the planner's view of the plan) and the URS-W3-020
performance budget the orchestrator measures at fan-in: the board's read API must serve a
200-order schedule in pages, formatted server-side, well inside ≤ 2 s.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest
from test_w3_scheduling_support import (
	FIRST_ORDER,
	LINE,
	PLAN_START,
	as_planner,
	draft_schedule,
)

frappe = pytest.importorskip("frappe")
board = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.board")
lifecycle = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.lifecycle")

BOARD_PAGE = "schedule-board"
ORDER_COUNT = 200
BUDGET_SECONDS = 2.0


def _large_schedule(site, count: int = ORDER_COUNT) -> str:
	"""A `count`-order schedule, built directly so the budget is measured, not the seeding."""
	doc = frappe.new_doc("Line Schedule")
	doc.production_line = LINE
	doc.planned_start = PLAN_START
	doc.schedule_state = "Draft"
	start = datetime(2026, 3, 2, 6, 0)
	for index in range(count):
		end = start + timedelta(minutes=495)
		doc.append(
			"entries",
			{
				"sequence": (index + 1) * 10,
				"work_order": FIRST_ORDER,
				"production_item": "RW-CHM-0003",
				"quantity": 500,
				"exec_state": "Accepted",
				"realization_min": 495,
				"changeover_min": 0 if index == 0 else 45,
				"planned_start": start,
				"planned_end": end,
			},
		)
		start = end + timedelta(minutes=45)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def test_board_page_is_installed_for_the_planner(site):
	"""URS-W3-005 / TC-W3-006 — the board ships as a committed page with planner access."""
	page = site.get_doc("Page", BOARD_PAGE)
	assert page.module == "Manufacturing Core"
	assert "Rheinwerk Planner" in {row.role for row in page.roles}


def test_head_and_rows_are_german_first(site):
	"""URS-W3-022 / TC-W3-006 — labels German, dates DD.MM.YYYY, masses in kg."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	head = board.board_head(schedule.name)
	assert head["schedule_state_label"] == "Entwurf"
	assert head["schedule_state_indicator"] == "orange"
	assert head["allowed_targets"] == ["Freigegeben", "Abgelehnt"] or set(head["allowed_targets"]) == {
		"Freigegeben",
		"Abgelehnt",
	}
	assert head["planned_start"] == "02.03.2026 06:00"

	page = board.board_rows(schedule.name)
	row = page["rows"][0]
	assert row["work_order"] == FIRST_ORDER
	assert row["quantity"] == "500 kg"
	assert row["realization"] == "495 min"
	assert row["planned_start"] == "02.03.2026 06:00"


def test_state_pill_tracks_the_decision(site):
	"""URS-W3-005 AC-2 / TC-W3-006 — the pill shows label + tone, not colour alone."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	as_planner(site)
	lifecycle.approve(schedule.name, reason="Reihenfolge geprüft")
	head = board.board_head(schedule.name)
	assert (head["schedule_state_label"], head["schedule_state_indicator"]) == ("Freigegeben", "green")
	assert head["is_operative"] is True
	assert head["allowed_targets"] == []
	assert board.glossary() == {"Draft": "Entwurf", "Approved": "Freigegeben", "Rejected": "Abgelehnt"}


def test_operations_pane_shows_the_tj_tpz_breakdown(site):
	"""URS-W3-006 AC-2 / TC-W3-008 — the planner sees where the minutes come from."""
	schedule = draft_schedule(site, [FIRST_ORDER])
	operations = board.board_operations(schedule.name, FIRST_ORDER)
	assert [row["operation"] for row in operations] == ["MIX", "FILL"]
	assert operations[0]["tpz"] == "30 min"
	assert operations[0]["tj"] == "0,6 min/kg"
	assert operations[0]["duration"] == "330 min"


def test_two_hundred_orders_are_served_in_pages_inside_the_budget(site):
	"""URS-W3-020 AC-1 / TC-W3-024 — a 200-order board loads well inside ≤ 2 s."""
	name = _large_schedule(site)
	started = time.perf_counter()
	head = board.board_head(name)
	first = board.board_rows(name, 0, 100)
	second = board.board_rows(name, 100, 100)
	elapsed = time.perf_counter() - started

	assert head["total_entries"] == ORDER_COUNT
	assert first["total"] == ORDER_COUNT
	assert len(first["rows"]) == 100 and len(second["rows"]) == 100
	assert first["rows"][0]["sequence"] < second["rows"][0]["sequence"]
	assert elapsed < BUDGET_SECONDS, f"200-order board took {elapsed:.2f} s"


def test_rows_are_a_window_not_the_whole_document(site):
	"""URS-W3-020 AC-1 / TC-W3-024 — the client never receives all 200 rows at once."""
	name = _large_schedule(site)
	page = board.board_rows(name, 0, board.DEFAULT_PAGE_LENGTH)
	assert page["page_length"] == board.DEFAULT_PAGE_LENGTH
	assert len(page["rows"]) == board.DEFAULT_PAGE_LENGTH < ORDER_COUNT
