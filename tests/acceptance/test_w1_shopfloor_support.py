"""Shared helpers for the W1-7/W1-8 acceptance suites (URS-W1-026…029).

Not a test module in itself — it arranges the seeded production order so the anchor
spawns its MIX and FILL job cards, exactly as the planner journey leaves it for the
operator. Kept inside the `test_w1_shopfloor_*` footprint so `conftest.py` stays untouched
for the parallel wave children.
"""

from __future__ import annotations

from typing import Any

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"
OPERATOR_USER = "o.weber@rheinwerk-chemie.example"
VIEWER_USER = "b.vogel@rheinwerk-chemie.example"
CLERK_USER = "w.braun@rheinwerk-chemie.example"
MIX = "MIX"
FILL = "FILL"


def require_order(site: Any, name: str = FIRST_ORDER) -> Any:
	"""The seeded production order, skipping when the site was not seeded."""
	import pytest

	if not site.db.exists("Work Order", name):
		pytest.skip(f"programme fixture {name} not seeded on this site")
	return site.get_doc("Work Order", name)


def running_order(site: Any, name: str = FIRST_ORDER) -> Any:
	"""The seeded order submitted with its routing operations, `exec_state` In Progress.

	Submitting the anchor Work Order is what spawns the job cards (ERPNext
	`work_order.py` → `create_job_card`), so the operator journey starts from here.
	"""
	doc = require_order(site, name)
	if doc.docstatus == 0:
		if not doc.get("operations"):
			doc.set_work_order_operations()
		doc.flags.ignore_permissions = True
		doc.save()
		doc.submit()
		doc.reload()
	set_exec_state(site, doc, "In Progress")
	return doc


def set_exec_state(site: Any, doc: Any, state: str) -> Any:
	"""Force `exec_state` (bypassing the machine) so a test starts from a known state."""
	site.db.set_value("Work Order", doc.name, "exec_state", state, update_modified=False)
	doc.reload()
	return doc


def job_card(site: Any, order: Any, operation: str) -> Any:
	"""The job card of one operation on the running order."""
	import pytest

	name = site.db.get_value("Job Card", {"work_order": order.name, "operation": operation}, "name")
	if not name:
		pytest.skip(f"no job card for operation {operation} on {order.name}")
	doc = site.get_doc("Job Card", name)
	if doc.docstatus == 0 and (doc.time_logs or doc.is_paused):
		# Start every journey from an untouched card, whatever a demo session left behind.
		doc.set("time_logs", [])
		doc.is_paused = 0
		doc.status = "Open"
		doc.total_completed_qty = 0
		doc.save(ignore_permissions=True)
		doc.reload()
	return doc


def as_operator(site: Any) -> None:
	"""Act as O. Weber, who holds the shop-floor operator role only."""
	site.set_user(OPERATOR_USER)


def test_support_module_exposes_helpers():
	"""Guard so this module keeps its documented helper surface for the W1-7 suites."""
	assert callable(running_order) and callable(job_card) and callable(set_exec_state)
