"""TC-W1-006 / TC-W1-030 — the acceptance-gate rule (offline).

Verifies **URS-W1-005** AC-1 (missing `production_line`), AC-2 (inconsistent planned
range), AC-3 (complete order accepted) and AC-4 (parity with the W0 characterisation
contract `CHAR-ORDER-ACCEPT-01`) against
`rheinwerk_mes.execution_gating.contracts` — the rule the Frappe gate and the
characterisation harness both run. Orders are legacy-shaped, exactly as the W0 fixtures
hold them.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from rheinwerk_mes.execution_gating.contracts import (
	DATES_ORDER_OVERDUE,
	FIELD_REQUIRED,
	evaluate_order_acceptance,
	format_date,
	missing_fields,
	parse_date,
)

#: PO-2026-0001 as TC-W1-006 step 3 leaves it: dates 10.03.2026–12.03.2026, LINE-1 and
#: the Accepted recipe BOM-RW-CHM-0003-001.
ACCEPTABLE_ORDER = {
	"number": "PO-2026-0001",
	"date_from": "10.03.2026",
	"date_to": "12.03.2026",
	"production_line": "LINE-1",
	"technology": "BOM-RW-CHM-0003-001",
}

FIXTURE = Path(__file__).resolve().parents[1] / "characterisation" / "fixtures" / "order_acceptance.json"


def test_acceptance_refused_when_production_line_is_missing():
	"""URS-W1-005 AC-1 / TC-W1-006 step 1 — PO-2026-0002 without a production line."""
	order = dict(ACCEPTABLE_ORDER, number="PO-2026-0002", production_line=None)

	verdict = evaluate_order_acceptance(order)

	assert verdict.allowed is False
	assert verdict.errors == (FIELD_REQUIRED,)
	assert [spec.canonical for spec in missing_fields(order)] == ["production_line"]


def test_acceptance_refused_when_recipe_reference_is_missing():
	"""URS-W1-005 — the recipe reference (anchor `bom_no`) is required as well."""
	order = dict(ACCEPTABLE_ORDER, number="PO-2026-0002", technology=None)

	verdict = evaluate_order_acceptance(order)

	assert verdict.errors == (FIELD_REQUIRED,)
	assert [spec.canonical for spec in missing_fields(order)] == ["bom_no"]


def test_refusals_are_raised_in_legacy_declaration_order():
	"""URS-W1-005 AC-4 — `OrderStateValidationService.java:44-47` field order is behaviour."""
	order = {"number": "PO-2026-0002"}

	assert [spec.legacy for spec in missing_fields(order)] == [
		"date_to",
		"date_from",
		"production_line",
		"technology",
	]
	assert evaluate_order_acceptance(order).errors == (FIELD_REQUIRED,) * 4


def test_acceptance_refused_when_planned_range_is_inconsistent():
	"""URS-W1-005 AC-2 / TC-W1-006 step 2 — start 15.03.2026, end 14.03.2026."""
	order = dict(
		ACCEPTABLE_ORDER,
		number="PO-2026-0002",
		date_from="15.03.2026",
		date_to="14.03.2026",
	)

	verdict = evaluate_order_acceptance(order)

	assert verdict.allowed is False
	assert verdict.errors == (DATES_ORDER_OVERDUE,)


def test_acceptance_refused_when_planned_range_has_zero_length():
	"""URS-W1-005 AC-2 — `OrderStateService.java:47-59` requires the end *after* the start."""
	order = dict(ACCEPTABLE_ORDER, date_from="10.03.2026", date_to="10.03.2026")

	assert evaluate_order_acceptance(order).errors == (DATES_ORDER_OVERDUE,)


def test_missing_and_inconsistent_dates_are_reported_together():
	"""URS-W1-005 — required fields first, then the range refusal."""
	order = dict(
		ACCEPTABLE_ORDER,
		production_line=None,
		date_from="15.03.2026",
		date_to="14.03.2026",
	)

	assert evaluate_order_acceptance(order).errors == (FIELD_REQUIRED, DATES_ORDER_OVERDUE)


def test_complete_order_is_accepted():
	"""URS-W1-005 AC-3 / TC-W1-006 step 3 — PO-2026-0001 passes the gate."""
	verdict = evaluate_order_acceptance(ACCEPTABLE_ORDER)

	assert verdict.allowed is True
	assert verdict.errors == ()


def test_planned_dates_are_read_from_frappe_and_german_first_values():
	"""URS-W1-005 — the rule reads `date`/`datetime`, ISO text and DD.MM.YYYY alike."""
	assert parse_date("10.03.2026") == parse_date("2026-03-10") == parse_date(date(2026, 3, 10))
	assert parse_date(None) is None
	assert parse_date("") is None
	assert format_date("2026-03-10 06:00:00") == "10.03.2026"

	order = dict(ACCEPTABLE_ORDER, date_from=date(2026, 3, 12), date_to=date(2026, 3, 10))
	assert evaluate_order_acceptance(order).errors == (DATES_ORDER_OVERDUE,)


@pytest.mark.skipif(not FIXTURE.exists(), reason="W0 characterisation fixtures not present")
def test_w0_characterisation_acceptance_contract_passes_against_the_target():
	"""URS-W1-005 AC-4 / TC-W1-030 step 2 — every `CHAR-ORDER-ACCEPT-01` case still holds.

	The harness resolves this module as the contract's target implementation; this test
	pins the same fixture cases so the parity is checked from the W1 side too.
	"""
	cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]

	for case in cases:
		verdict = evaluate_order_acceptance(case["order"])
		assert verdict.allowed is bool(case["expected"]["allowed"]), case["id"]
		assert list(verdict.errors) == list(case["expected"]["errors"]), case["id"]
