"""Whitelisted read API behind the planning-queue Desk page (URS-W3-001/004).

Thin transport over `plan.planning_queue`; the page (`page/planning_queue`) renders the
returned model. Kept separate from `plan` so the page has one stable `@frappe.whitelist`
entrypoint and the core model stays callable server-side and from tests without a request.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.manufacturing_core.planning.plan import planning_queue


@frappe.whitelist()
def get_planning_queue() -> dict[str, list[dict[str, object]]]:
	"""Planning queue for the Desk page: submitted plans and their generated orders."""
	frappe.has_permission("Production Plan", "read", throw=True)
	return planning_queue()
