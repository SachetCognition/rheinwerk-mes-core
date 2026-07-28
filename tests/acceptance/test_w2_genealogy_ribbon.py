"""TC-W2-004 / TC-W2-005 — Trace Ribbon rendering, interaction and print (W2-1).

Verifies **URS-W2-003 AC-1…4**: the horizontal supplier→focus→downstream layout, the
keyboard path (arrows/Enter/Esc) with preserved expansion state, monospaced batch IDs with
status indicators, the hard visual break of a blocked branch, and print parity in which the
blocked state stays identifiable without colour.

The layout/interaction assertions read the shipped page and stylesheet, because the ribbon's
design conformance lives in that markup — `rheinwerk-mes-design-SKILL.md` pattern 4.
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import BATCH_A2, BATCH_C1, require_fixture, require_w2_schema, set_state

pytest.importorskip("frappe")
ribbon = pytest.importorskip("rheinwerk_mes.genealogy.ribbon")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")

PAGE = "rheinwerk_mes/genealogy/page/trace_ribbon/trace_ribbon.js"
STYLES = "rheinwerk_mes/public/css/trace_ribbon.css"


@pytest.fixture
def focused(site):
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	return ribbon.ribbon(BATCH_C1)


def test_ribbon_places_suppliers_left_focus_centre_downstream_right(focused):
	"""URS-W2-003 AC-1 / TC-W2-004 step 1 — the three ribbon zones carry the trace."""
	assert focused["focus"]["batch"] == BATCH_C1
	assert {chip["side"] for chip in focused["left"]} == {"left"}
	assert BATCH_A2 in {chip["batch"] for chip in focused["left"]}
	assert all(chip["level"] >= 1 for chip in focused["left"])
	assert focused["printable"] is True


def test_chips_carry_monospaced_ids_and_icon_label_colour_status(focused, repo_root):
	"""URS-W2-003 AC-1 / TC-W2-004 step 3 — chip composition, never colour alone."""
	chip = focused["left"][0]
	pill = chip["pills"][0]
	assert pill["label"] and pill["icon"] and pill["tone"], "icon + label + colour"
	assert chip["expiry_date"] is None or "." in chip["expiry_date"], "DD.MM.YYYY"

	styles = (repo_root / STYLES).read_text(encoding="utf-8")
	assert "IBM Plex Mono" in styles, "batch IDs are monospaced"
	assert ".rw-chip__pills" in styles


def test_keyboard_path_recentres_and_preserves_expansion(repo_root):
	"""URS-W2-003 AC-3 / TC-W2-004 steps 2+4 — arrows, Enter, Esc and the shortcut hint."""
	page = (repo_root / PAGE).read_text(encoding="utf-8")
	assert 'event.key === "ArrowRight"' in page and 'event.key === "ArrowLeft"' in page
	assert 'event.key === "Enter"' in page and "this.load(chips[this.selected].batch)" in page
	assert 'event.key === "Escape"' in page
	assert "this.expanded.add(batch)" in page, "expansion state survives a recentre"
	assert "__(" in page and "frappe.utils.escape_html" in page


def test_blocked_branch_breaks_hard_and_stays_readable_in_print(site, repo_root):
	"""URS-W2-003 AC-2/AC-4 / TC-W2-005 steps 1-2 — red break plus icon + label."""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A2)
	set_state(site, BATCH_A2, qa_state.BLOCKED)

	model = ribbon.ribbon(BATCH_C1)
	blocked = [chip for chip in model["left"] if chip["batch"] == BATCH_A2][0]
	assert blocked["branch_break"] is True
	pill = blocked["pills"][0]
	assert (pill["label"], pill["tone"], pill["icon"]) == ("Gesperrt", "red", "octagon")

	styles = (repo_root / STYLES).read_text(encoding="utf-8")
	assert '.rw-chip[data-break="1"]' in styles and "--rw-signal-red" in styles
	assert "repeating-linear-gradient" in styles, "the break survives greyscale"
	assert "@media print" in styles and ".rw-chip {" in styles.split("@media print")[1]
