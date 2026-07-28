"""Shared helpers for the W3-2 scheduling acceptance suites (URS-W3-005…009).

Not a test module in itself — it holds what the `test_w3_scheduling_*.py` suites share, so
`conftest.py` stays untouched for the parallel wave children (same pattern as
`test_w1_exec_state_support.py`).
"""

from __future__ import annotations

from typing import Any

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
LINE = "LINE-1"
MIX_WORK_CENTRE = "MIX-01"
FILL_WORK_CENTRE = "FILL-01"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"
OPERATOR_USER = "o.weber@rheinwerk-chemie.example"
PLAN_START = "2026-03-02 06:00:00"

#: URS-W3-006 AC-1: MIX = 30 + 500 × 0,6, FILL = 15 + 500 × 0,3, order total 495 min.
MIX_MINUTES = 330
FILL_MINUTES = 165
ORDER_MINUTES = 495

#: The seeded LINE-1 inter-batch flush (URS-W3-007 AC-1).
CHANGEOVER_MINUTES = 45


def require_fixture(site: Any, doctype: str, name: str) -> Any:
	"""Return the seeded document, skipping when the site was not seeded."""
	import pytest

	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def require_norms(site: Any) -> None:
	"""Skip unless the TJ/TPZ and changeover norms of LINE-1 are seeded."""
	import pytest

	for operation in ("MIX", "FILL"):
		if not site.db.exists("Operation Time Norm", {"operation": operation, "production_line": LINE}):
			pytest.skip(f"TJ/TPZ norm for {operation} not seeded on this site")
	if not site.db.exists("Line Changeover Norm", {"production_line": LINE}):
		pytest.skip("changeover norm for LINE-1 not seeded on this site")


def accepted_order(site: Any, name: str = FIRST_ORDER) -> Any:
	"""The seeded order submitted and forced into `exec_state` Accepted (URS-W3-005 AC-1)."""
	doc = require_fixture(site, "Work Order", name)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
		doc.reload()
	set_exec_state(site, name, "Accepted")
	doc.reload()
	return doc


def set_exec_state(site: Any, work_order: str, state: str) -> None:
	"""Force `exec_state` (bypassing the W1 machine) so a test starts from a known state."""
	site.db.set_value("Work Order", work_order, "exec_state", state, update_modified=False)


def as_planner(site: Any) -> None:
	"""Act as P. Krüger, the planner persona who decides schedules."""
	import pytest

	if not site.db.exists("User", PLANNER_USER):
		pytest.skip("planner persona not seeded on this site")
	site.set_user(PLANNER_USER)


def draft_schedule(
	site: Any,
	work_orders: list[str] | None = None,
	planned_start: str | None = PLAN_START,
) -> Any:
	"""A Draft `Line Schedule` for LINE-1 over the given (default: both) fixture orders."""
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	require_norms(site)
	names = work_orders if work_orders is not None else [FIRST_ORDER, SECOND_ORDER]
	for name in names:
		accepted_order(site, name)
	schedule = lifecycle.create_schedule(LINE, names, planned_start)
	return site.get_doc("Line Schedule", schedule)


def entry_for(schedule: Any, work_order: str) -> Any:
	"""The schedule entry of `work_order`."""
	rows = [row for row in schedule.entries if row.work_order == work_order]
	assert rows, f"{work_order} is not in schedule {schedule.name}"
	return rows[0]


def operation_for(schedule: Any, work_order: str, operation: str) -> Any:
	"""The scheduled operation row of `work_order`/`operation`."""
	rows = [row for row in schedule.operations if row.work_order == work_order and row.operation == operation]
	assert rows, f"{work_order}/{operation} is not in schedule {schedule.name}"
	return rows[0]


def gate_log(site: Any, gate: str, reference_name: str) -> list[dict[str, Any]]:
	"""Audit rows of a gate for one record, newest first (URS-W3-021)."""
	return site.get_all(
		"Execution Gate Log",
		filters={"gate": gate, "reference_name": reference_name},
		fields=["gate", "outcome", "rule", "from_state", "to_state", "detail"],
		order_by="creation desc",
	)


def test_support_module_exposes_helpers():
	"""Guard so this module keeps its documented helper surface for the W3-2 suites."""
	assert callable(draft_schedule) and callable(accepted_order) and callable(gate_log)
