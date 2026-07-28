"""Order state gating contracts — CHAR-ORDER-ACCEPT-01, CHAR-ORDER-COMPLETE-01.

URS-W0-012 (AC-1, AC-2) · TC-W0-014 steps 1-2.
Legacy baseline: `mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/
states/OrderStateValidationService.java:44-47` (acceptance) and `:54-63` (completion) in
`SachetCognition/Chem_mes@master`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import evaluate_order_acceptance, evaluate_order_completion
from ..registry import Contract, register


def _check_gate(resolution: Resolution, case: Mapping[str, Any]) -> None:
	verdict = resolution.callable_(case["order"])
	expected_allowed = bool(case["expected"]["allowed"])
	expected_errors = tuple(case["expected"]["errors"])
	assert verdict.allowed is expected_allowed, (
		f"{case['id']}: expected allowed={expected_allowed}, got {verdict.allowed} "
		f"(implementation: {resolution.source})"
	)
	assert tuple(verdict.errors) == expected_errors, (
		f"{case['id']}: expected errors {expected_errors}, got {tuple(verdict.errors)} "
		f"(implementation: {resolution.source})"
	)


ORDER_ACCEPTANCE = register(
	Contract(
		id="CHAR-ORDER-ACCEPT-01",
		title="Order acceptance refused when dateFrom/dateTo/production line/technology missing",
		concern="order_acceptance",
		legacy_source="OrderStateValidationService.java:44-47",
		fixture="order_acceptance.json",
		fallback=evaluate_order_acceptance,
		checker=_check_gate,
		urs_ids=("URS-W0-012",),
		tc_ids=("TC-W0-014",),
	)
)

ORDER_COMPLETION = register(
	Contract(
		id="CHAR-ORDER-COMPLETE-01",
		title="Order completion refused when doneQuantity = 0",
		concern="order_completion",
		legacy_source="OrderStateValidationService.java:54-63",
		fixture="order_completion.json",
		fallback=evaluate_order_completion,
		checker=_check_gate,
		urs_ids=("URS-W0-012",),
		tc_ids=("TC-W0-014",),
	)
)
