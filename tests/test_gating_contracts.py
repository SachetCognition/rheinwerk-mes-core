"""Offline parity checks for the order-gating contracts (W1-2, no Frappe site).

The acceptance gate (URS-W1-005/006) and completion gate (URS-W1-007) map the anchor Work
Order onto these pure functions; the recipe-Accepted decision itself is the trivial
`gov_state == Accepted` check exercised by the site-backed suite. These offline cases pin
the contract's legacy-key verdicts so the decision logic is verifiable without a site.
"""

from __future__ import annotations

from rheinwerk_mes.execution_gating import contracts


def test_acceptance_allowed_when_all_references_present():
	order = {
		"date_from": "10.03.2026",
		"date_to": "12.03.2026",
		"production_line": "LINE-1",
		"technology": "BOM-RW-CHM-0003-001",
	}
	assert contracts.evaluate_order_acceptance(order).allowed


def test_acceptance_refused_lists_one_key_per_missing_field():
	verdict = contracts.evaluate_order_acceptance({"technology": "BOM-RW-CHM-0003-001"})
	assert not verdict.allowed
	assert verdict.errors == (contracts.FIELD_REQUIRED,) * 3


def test_acceptance_refused_when_end_not_after_start():
	order = {
		"date_from": "15.03.2026",
		"date_to": "14.03.2026",
		"production_line": "LINE-1",
		"technology": "BOM-RW-CHM-0003-001",
	}
	verdict = contracts.evaluate_order_acceptance(order)
	assert not verdict.allowed
	assert contracts.DATES_ORDER_OVERDUE in verdict.errors


def test_completion_refused_with_zero_output():
	order = {"date_from": "10.03.2026", "date_to": "12.03.2026", "done_quantity": 0}
	verdict = contracts.evaluate_order_completion(order)
	assert not verdict.allowed
	assert contracts.DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO in verdict.errors
