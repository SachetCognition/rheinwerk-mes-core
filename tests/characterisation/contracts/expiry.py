"""Expiry-policy divergence contract — CHAR-EXPIRY-ISSUE-01.

URS-W1-030 (AC-2) · TC-W1-033. Legacy baseline: `mes-plugins/
mes-plugins-material-flow-resources/src/main/java/com/qcadoo/mes/materialFlowResources/
service/ResourceManagementServiceImpl.java:1015-1027` orders resources by expiry under
FEFO but the issue path never compares expiry to the posting date — expired stock is
issuable at Plant A (`SachetCognition/Chem_mes@master`).

Unlike every other registered contract this one is expected **not** to hold: the estate
refuses expired consumption (`stock_ledger_entry.py:287-299` extended by
`rheinwerk_mes.execution_gating.expiry` and `.allocation`). The contract exists so the
delta is measured and classified as an intentional, signed-off divergence rather than
silently absent — see `docs/decisions/DEC-W1-030-expiry-policy.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import evaluate_expired_issue
from ..registry import Contract, Divergence, register


def _check_issue(resolution: Resolution, case: Mapping[str, Any]) -> None:
	verdict = resolution.callable_(case["issue"])
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


EXPIRY_ISSUE = register(
	Contract(
		id="CHAR-EXPIRY-ISSUE-01",
		title="Expired resource issuable under Plant A's FEFO-advisory behaviour",
		concern="expired_issue",
		legacy_source="ResourceManagementServiceImpl.java:1015-1027",
		fixture="expiry_issue.json",
		fallback=evaluate_expired_issue,
		checker=_check_issue,
		urs_ids=("URS-W1-030",),
		tc_ids=("TC-W1-033",),
		divergence=Divergence(
			decision="URS-W1-030",
			record="docs/decisions/DEC-W1-030-expiry-policy.md",
			summary=(
				"Estate-wide hard stop on consuming expired batches; Plant A issued them under "
				"FEFO-advisory ordering."
			),
		),
	)
)
