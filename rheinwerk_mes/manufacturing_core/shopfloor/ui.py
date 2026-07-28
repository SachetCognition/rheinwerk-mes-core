"""UI profile endpoints for the shop-floor screens (URS-W1-035, URS-W1-022).

The page assets never hard-code density numbers or legacy names: they ask the server, so
Desk/Terminal tokens, the shortcut sheet and the legacy-bridge hints have exactly one
definition (`terminal.py`, `legacy_bridge.py`) that the conformance tests also read.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.manufacturing_core.shopfloor import legacy_bridge, terminal


@frappe.whitelist()
def mode_profile(mode: str | None = None, workstation: str | None = None) -> dict[str, Any]:
	"""Density tokens for the requested mode, auto-selected from the station profile."""
	if not mode and workstation:
		mode = terminal.resolve_mode(frappe.db.get_value("Workstation", workstation, "station_profile"))
	resolved = mode if mode in terminal.MODES else terminal.DESK
	return {"mode": resolved, **terminal.mode_tokens(resolved)}


@frappe.whitelist()
def screen_profile(work_order: str | None = None, workstation: str | None = None) -> dict[str, Any]:
	"""Everything a W1 screen needs to render itself: density, pills and legacy hints."""
	profile = mode_profile(workstation=workstation)
	profile["legacy_hints"] = {
		"Work Order": legacy_bridge.legacy_hints("Work Order"),
		"Job Card": legacy_bridge.legacy_hints("Job Card"),
	}
	if work_order:
		state = frappe.db.get_value("Work Order", work_order, "exec_state")
		profile["exec_state_pill"] = terminal.state_pill(state)
	return profile
