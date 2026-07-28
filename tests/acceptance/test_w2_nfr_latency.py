"""TC-W2-046 / TC-W2-047 — trace and scan latency of the W2 surfaces.

Verifies **URS-W2-033** (a 200-node Trace Ribbon server-confirmed ≤ 2 s p95, scan-to-
confirmation ≤ 300 ms p95, progress shown on the control beyond 100 ms and no optimistic
confirmation of a gated action) through **TC-W2-046** and **TC-W2-047** of
`docs/test/TST-W2-traceability-quality.md`.

Automated residue: the server halves are measured here — a synthetic 200-node genealogy for
the ribbon, repeated scan resolutions for the terminal. The *browser* halves (sub-100 ms
paint, progress rendered on the control itself) are asserted by contract against the page
assets, with the wall-clock measurement on plant terminal hardware staying a manual check
recorded in the W2 evidence pack, exactly as W1 handled TC-W1-035.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

frappe = pytest.importorskip("frappe")
ribbon = pytest.importorskip("rheinwerk_mes.genealogy.ribbon")
scanner = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.scanner")

RIBBON_JS = Path("rheinwerk_mes/genealogy/page/trace_ribbon/trace_ribbon.js")
"""Relative to the repository root — resolved through the `repo_root` fixture."""

BATCH = "BATCH-C-1001"
SCAN_BATCH = "BATCH-A-0001"

RIBBON_RUNS = 20
RIBBON_BUDGET_MS = 2000.0
RIBBON_NODES = 200

SCAN_RUNS = 50
SCAN_BUDGET_MS = 300.0

#: The node count the ribbon must survive is built as a fan of children under one root, so
#: the tree is wide rather than deep — the shape the URS names (200 nodes, ≤ 5 levels).
FAN_ITEM = "RW-CHM-0003"


def _p95(samples: list[float]) -> float:
	ordered = sorted(samples)
	return ordered[min(int(round(0.95 * len(ordered))) - 1, len(ordered) - 1)]


def _require(site: Any, doctype: str, name: str) -> None:
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")


def _fan_out(site: Any, root: str, count: int) -> None:
	"""Give `root` `count` descendants so the ribbon has a 200-node tree to render.

	The links are written directly onto the synthetic children (the child owns its
	`consumed` row, as `links.rebuild_links_for_work_order` writes them) rather than through
	a posted Stock Entry: this is a latency fixture, not a genealogy behaviour case.
	"""
	from rheinwerk_mes.genealogy import links

	for index in range(count):
		child = f"NFR-BATCH-{index:04d}"
		if site.db.exists("Batch", child):
			continue
		doc = site.get_doc(
			{
				"doctype": "Batch",
				"batch_id": child,
				"item": FAN_ITEM,
			}
		)
		doc.append(
			links.LINK_FIELD,
			{"direction": links.CONSUMED, "batch": root, "item": FAN_ITEM, "qty": 1.0, "uom": "Kg"},
		)
		doc.insert(ignore_permissions=True)


def test_two_hundred_node_ribbon_stays_inside_the_budget(site):
	"""URS-W2-033 AC-1 / TC-W2-046 — p95 server response of the ribbon ≤ 2 s over 20 runs."""
	_require(site, "Batch", BATCH)
	if not site.get_meta("Batch").get_field("genealogy_links"):
		pytest.skip("W2 genealogy fields not installed on this site")
	_fan_out(site, BATCH, RIBBON_NODES)

	durations = []
	for _run in range(RIBBON_RUNS):
		started = time.perf_counter()
		model = ribbon.ribbon(BATCH)
		durations.append((time.perf_counter() - started) * 1000)
		assert model["focus"]["batch"] == BATCH

	measured = _p95(durations)
	assert measured <= RIBBON_BUDGET_MS, f"p95 ribbon latency {measured:.0f} ms exceeds the budget"


def test_fifty_scans_stay_inside_the_budget(site):
	"""URS-W2-033 AC-2 / TC-W2-047 — p95 scan-to-server-confirmation ≤ 300 ms over 50 scans."""
	_require(site, "Batch", SCAN_BATCH)
	durations = []
	for _run in range(SCAN_RUNS):
		started = time.perf_counter()
		result = scanner.scan(SCAN_BATCH)
		durations.append((time.perf_counter() - started) * 1000)
		assert result["recognised"] is True

	measured = _p95(durations)
	assert measured <= SCAN_BUDGET_MS, f"p95 scan latency {measured:.0f} ms exceeds the budget"


def test_ribbon_page_shows_progress_and_never_confirms_optimistically(repo_root):
	"""URS-W2-033 AC-1 / TC-W2-046 — feedback lives on the control, data comes from the server."""
	asset = repo_root / RIBBON_JS
	if not asset.exists():
		pytest.skip("Trace Ribbon page asset not present in this checkout")
	source = asset.read_text(encoding="utf-8")
	assert "set_busy" in source, "the control must show it is working"
	assert "disabled" in source, "a busy control is disabled, so no second request is invited"
	assert '.call("rheinwerk_mes.genealogy.ribbon.ribbon"' in source, (
		"ribbon data must be server-confirmed, never assembled client-side"
	)
