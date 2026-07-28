"""TC-W1-035 — shop-floor interaction latency under load.

Verifies **URS-W1-032** (p95 server-confirmed scan latency ≤ 300 ms; UI feedback < 100 ms;
gated actions never optimistically confirmed) through **TC-W1-035** of
`docs/test/TST-W1-production-core.md`.

Automated residue: step 1 is measured here as 100 sequential server-side scan resolutions.
The *browser* half — sub-100 ms paint of the feedback and progress rendered on the control
itself under an artificially delayed server (step 2) — is asserted by contract against the
page asset; the wall-clock browser measurement on plant terminal hardware stays a manual
check recorded in the W1 evidence pack.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from test_w1_shopfloor_support import FIRST_ORDER, as_operator, running_order

frappe = pytest.importorskip("frappe")
scanner = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.scanner")

PAGE_JS = Path("rheinwerk_mes/manufacturing_core/page/shop_floor_terminal/shop_floor_terminal.js")
SCAN_COUNT = 100
P95_BUDGET_MS = 300.0


def _p95(samples: list[float]) -> float:
	ordered = sorted(samples)
	return ordered[min(int(round(0.95 * len(ordered))) - 1, len(ordered) - 1)]


def test_hundred_sequential_scans_stay_inside_the_budget(site):
	"""URS-W1-032 AC-1 / TC-W1-035 step 1 — p95 server-confirmed scan ≤ 300 ms."""
	running_order(site)
	batch = site.db.get_value("Batch", {}, "name") or FIRST_ORDER
	as_operator(site)

	durations = []
	for _ in range(SCAN_COUNT):
		started = time.perf_counter()
		result = scanner.scan(batch)
		durations.append((time.perf_counter() - started) * 1000)
		assert result["recognised"] is True

	measured_p95 = _p95(durations)
	assert measured_p95 <= P95_BUDGET_MS, f"p95 scan latency {measured_p95:.1f} ms exceeds the budget"


def test_scan_response_reports_its_own_server_time(site):
	"""URS-W1-032 — every scan answer carries the measurement the budget is judged on."""
	running_order(site)
	as_operator(site)
	result = scanner.scan(FIRST_ORDER)
	assert 0 <= result["server_ms"] <= P95_BUDGET_MS


def test_gated_actions_are_never_optimistically_confirmed(repo_root):
	"""URS-W1-032 AC-2 / TC-W1-035 step 2 — progress on the control, success after the server."""
	source = (repo_root / PAGE_JS).read_text(encoding="utf-8")
	action = source.split("call_job_action(action, args, control) {")[1]
	assert "rw-btn--busy" in action, "progress is rendered on the control itself"
	assert action.index("rw-btn--busy") < action.index("frappe"), (
		"the busy state is shown before the server call is issued"
	)
	assert action.index("frappe") < action.index("this.render_queue();"), (
		"the result is only rendered once the server has confirmed"
	)
	assert "rw-terminal--pending" in source, "the scan field shows immediate UI feedback"
