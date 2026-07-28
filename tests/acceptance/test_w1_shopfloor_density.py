"""TC-W1-039 — Desk/Terminal mode conformance on the W1 screens.

Verifies **URS-W1-035** (both density modes render the same information; Terminal ≥16px
base and ≥48px targets; status pills never colour-only; `?` opens the shortcut sheet with
the complete keyboard path) through **TC-W1-039** of `docs/test/TST-W1-production-core.md`.

Automated as token, asset and payload assertions. The visual grayscale review of the
rendered screens on plant hardware stays a manual check recorded in the W1 evidence pack;
the screenshots are attached to the delivery PR.
"""

from __future__ import annotations

from pathlib import Path

import pytest

frappe = pytest.importorskip("frappe")
terminal = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.terminal")
ui = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.ui")

PAGE_JS = Path("rheinwerk_mes/manufacturing_core/page/shop_floor_terminal/shop_floor_terminal.js")
PAGE_CSS = Path("rheinwerk_mes/public/css/shopfloor.css")


def test_terminal_mode_is_larger_and_hides_nothing():
	"""URS-W1-035 AC-1 / TC-W1-039 step 1 — ≥16px base, ≥48px targets, same fields."""
	desk = terminal.mode_tokens(terminal.DESK)
	term = terminal.mode_tokens(terminal.TERMINAL)

	assert term["base_font_px"] >= 16
	assert term["min_target_px"] >= 48
	assert term["base_font_px"] > desk["base_font_px"]
	assert term["fields"] == desk["fields"], "terminal mode enlarges, it never hides"


def test_mode_is_auto_selected_by_the_station_profile(site):
	"""URS-W1-035 — the station profile picks the mode; Desk stays the default."""
	assert terminal.resolve_mode("Terminal") == terminal.TERMINAL
	assert terminal.resolve_mode(None) == terminal.DESK
	profile = site.db.get_value("Workstation", {"name": "MIX-01"}, "station_profile")
	if profile:
		assert ui.mode_profile(workstation="MIX-01")["mode"] == terminal.resolve_mode(profile)


def test_status_pills_are_never_colour_only():
	"""URS-W1-035 AC-2 / TC-W1-039 step 2 — every pill carries an icon and a label."""
	for state in ("Pending", "In Progress", "Completed", "On Hold"):
		pill = terminal.state_pill(state)
		assert pill["icon"] and pill["label"]


def test_shortcut_sheet_publishes_the_complete_keyboard_path(repo_root):
	"""URS-W1-035 AC-3 / TC-W1-039 step 3 — `?` opens the sheet; Enter/Esc/arrows work."""
	keys = {row["keys"] for row in terminal.mode_tokens(terminal.TERMINAL)["shortcuts"]}
	assert {"Enter", "Esc", "↑ / ↓", "?"} <= keys

	source = (repo_root / PAGE_JS).read_text(encoding="utf-8")
	assert 'event.key === "?"' in source and "show_shortcuts()" in source
	assert 'event.key === "Escape"' in source
	assert '"ArrowDown"' in source and '"ArrowUp"' in source


def test_stylesheet_mirrors_the_density_tokens(repo_root):
	"""URS-W1-035 AC-1 — the assets carry the same numbers as the server-side tokens."""
	css = (repo_root / PAGE_CSS).read_text(encoding="utf-8")
	term = terminal.MODES[terminal.TERMINAL]
	assert f"--rw-base-font: {term.base_font_px}px" in css
	assert f"--rw-target: {term.min_target_px}px" in css
	assert f"--rw-row-height: {term.row_height_px}px" in css
