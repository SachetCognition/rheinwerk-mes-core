"""TC-W1-029 — scanner-first identification on the shop-floor screens.

Verifies **URS-W1-028** (always-focused scan field, full-row visual + audible confirmation,
non-blocking inline error naming an unknown code) through **TC-W1-029** of
`docs/test/TST-W1-production-core.md`.

Automated residue: the *pointer-free* operation and the audible tone itself are properties
of the page assets, asserted here by contract — the scan resolver returns the highlight
target and the confirmation-sound key, and `shop_floor_terminal.js` is scanned for the
always-focused field and its keyboard-only path. Physically hearing the tone on plant
hardware stays a manual check recorded in the W1 evidence pack.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_w1_shopfloor_support import FIRST_ORDER, as_operator, running_order

frappe = pytest.importorskip("frappe")
scanner = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.scanner")

PAGE_JS = Path("rheinwerk_mes/manufacturing_core/page/shop_floor_terminal/shop_floor_terminal.js")


def test_scanning_an_order_loads_its_job_queue(site):
	"""URS-W1-028 AC-1 / TC-W1-029 step 1 — the scanned order resolves to its queue."""
	order = running_order(site)
	as_operator(site)

	result = scanner.scan(FIRST_ORDER)

	assert result["recognised"] is True
	assert result["kind"] == "work_order"
	assert result["name"] == order.name
	assert result["highlight"] == f"work_order:{order.name}"


def test_scanning_a_batch_confirms_visually_and_audibly(site):
	"""URS-W1-028 AC-2 / TC-W1-029 step 2 — full-row highlight plus confirmation tone."""
	batch = site.db.get_value("Batch", {}, "name")
	if not batch:
		pytest.skip("no batch fixture on this site")
	as_operator(site)

	result = scanner.scan(batch)

	assert result["recognised"] is True
	assert result["kind"] == "batch"
	assert result["highlight"] == f"batch:{batch}"
	assert result["confirm_sound"] == "scan-ok"


def test_unknown_code_is_a_focused_inline_error(site):
	"""URS-W1-028 AC-3 / TC-W1-029 step 3 — the code is named; the field keeps focus."""
	as_operator(site)

	result = scanner.scan("XX-0000")

	assert result["recognised"] is False
	assert "XX-0000" in result["message"]
	assert result["keep_focus"] is True


def test_terminal_page_keeps_the_scan_field_focused(repo_root):
	"""URS-W1-028 / TC-W1-029 — the page asset implements the always-focused scan field."""
	source = (repo_root / PAGE_JS).read_text(encoding="utf-8")
	assert 'data-ref="scan"' in source
	assert "focus_scan()" in source
	assert 'this.$scan.on("blur"' in source, "focus returns to the scan field after every blur"
	assert "beep()" in source, "successful scans are confirmed audibly"
