"""W2-9 — the scripted multi-level trace demonstration (EXIT-W2-1).

TC-W2-036 (URS-W2-028 AC-1, AC-2): blocking `BATCH-A-0002` must be visible downstream on both
finished-goods batches, the backward trace from `BATCH-C-1001` must reach the supplier lot at
level 2, quantities must be listed at every level — and the run's output must be the committed
wave-acceptance artefact, not a screenshot pasted by hand.

The demo itself lives in `tools/trace_demo` so the artefact and these assertions come from one
code path.
"""

from __future__ import annotations

import pytest

pytest.importorskip("frappe")
demo = pytest.importorskip("tools.trace_demo.demo")
trace = pytest.importorskip("rheinwerk_mes.genealogy.trace")
links = pytest.importorskip("rheinwerk_mes.genealogy.links")

ARTEFACT = "docs/evidence/W2-trace-demo.md"


@pytest.fixture
def demonstration(site):
	if not site.get_meta("Batch").get_field("qa_state"):
		pytest.skip("W2 genealogy schema not installed on this site")
	if not links.links_of(demo.FINISHED_BATCHES[0], links.CONSUMED):
		pytest.skip("genealogy fixture not seeded on this site")
	return demo.run()


def test_tc_w2_036_forward_trace_reaches_both_finished_batches_with_advisories(demonstration):
	"""TC-W2-036 step 1 (URS-W2-028 AC-1) — the block propagates to every consumer."""
	found = {node["batch"]: node for node in demonstration.forward_nodes()}
	for batch in demo.FINISHED_BATCHES:
		assert batch in found, f"{batch} not reached by the forward trace"
		assert demo.BLOCKED_BATCH in found[batch]["blocked_ancestors"]
		assert found[batch]["qty"] > 0, "the demo must list the quantity of every edge"


def test_tc_w2_036_backward_trace_reaches_the_supplier_lot_at_level_two(demonstration):
	"""TC-W2-036 step 1 (URS-W2-028 AC-1) — three levels, upstream direction."""
	by_batch = {node["batch"]: node for node in demonstration.backward_nodes()}
	assert by_batch[demo.BLOCKED_BATCH]["level"] == 1
	assert by_batch[demo.SUPPLIER_BATCH]["level"] == 2
	assert demonstration.levels() >= 3, "the demonstration must span at least three levels"


def test_tc_w2_036_artefact_is_committed_and_current(demonstration, repo_root):
	"""TC-W2-036 step 2 (URS-W2-028 AC-2) — the run's output is the acceptance artefact."""
	path = repo_root / ARTEFACT
	assert path.exists(), f"{ARTEFACT} missing — the demo output must be committed"
	assert path.read_text(encoding="utf-8") == demo.render_markdown(demonstration), (
		f"{ARTEFACT} is stale — regenerate it with `python -m tools.trace_demo.generate`"
	)
