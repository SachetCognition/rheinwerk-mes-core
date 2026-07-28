"""TC-W3-024 — the W3 performance budgets other than the schedule-board render.

Verifies **URS-W3-020** (dispatch scan server-confirmed ≤ 300 ms p95, an orders-in message
processed end to end ≤ 10 s, and planner actions that outrun 100 ms showing progress on the
control) through **TC-W3-024** of `docs/test/TST-W3-planning-boundary.md`. The 200-order board
render, step 1 of the same case, is measured by `test_w3_scheduling_board.py`.

The server halves are measured here; the browser half (progress rendered on the control the
planner pressed, wall-clock on plant terminal hardware) is asserted by contract against the
page asset, with the hardware reading staying a manual check recorded in the W3 evidence pack —
the same split W1 and W2 used for their latency cases.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from test_w3_boundary_support import loopback

frappe = pytest.importorskip("frappe")

BOARD_JS = Path("rheinwerk_mes/manufacturing_core/page/schedule_board/schedule_board.js")

SCAN_BATCH = "BATCH-C-1001"
SCAN_RUNS = 30
SCAN_BUDGET_MS = 300.0
ORDERS_IN_BUDGET_S = 10.0


def _p95(samples: list[float]) -> float:
	ordered = sorted(samples)
	return ordered[min(int(round(0.95 * len(ordered))) - 1, len(ordered) - 1)]


def test_dispatch_scan_is_confirmed_within_300_ms(site):
	"""URS-W3-020 AC-3 / TC-W3-024 step 3 — the clerk's scan resolves inside the budget."""
	dispatch = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.dispatch")
	if not site.db.exists("Batch", SCAN_BATCH):
		pytest.skip(f"programme fixture Batch {SCAN_BATCH} not seeded on this site")

	samples: list[float] = []
	for _run in range(SCAN_RUNS):
		started = time.perf_counter()
		resolved = dispatch.scan_for_dispatch(SCAN_BATCH)
		samples.append((time.perf_counter() - started) * 1000)
		assert resolved["batch"] == SCAN_BATCH

	measured = _p95(samples)
	assert measured <= SCAN_BUDGET_MS, f"dispatch scan p95 {measured:.0f} ms exceeds {SCAN_BUDGET_MS:.0f} ms"


def test_orders_in_is_processed_end_to_end_within_ten_seconds(site, monkeypatch):
	"""URS-W3-020 AC-4 / TC-W3-024 step 4 — an inbound demand lands well inside the budget."""
	from rheinwerk_mes.integration.boundary import contracts, inbound

	loopback(monkeypatch)
	started = time.perf_counter()
	result = inbound.play_fixture("erp-in-001-happy.json")
	elapsed = time.perf_counter() - started

	assert result.outcome == contracts.PROCESSED
	assert elapsed <= ORDERS_IN_BUDGET_S, f"orders-in took {elapsed:.1f} s, budget {ORDERS_IN_BUDGET_S:.0f} s"


def test_the_board_shows_progress_on_the_control_it_was_pressed_on(repo_root):
	"""URS-W3-020 AC-2 / TC-W3-024 step 2 — no silent wait on approve/resequence."""
	asset = repo_root / BOARD_JS
	if not asset.exists():
		pytest.skip("schedule board asset not present in this checkout")
	source = asset.read_text(encoding="utf-8")

	assert re.search(r"busy\(\s*\$control", source), (
		"a planner action beyond 100 ms must show progress on the control itself"
	)
