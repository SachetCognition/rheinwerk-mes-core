"""Audited transition entrypoint for the shop-floor screens (URS-W1-029, URS-W1-033).

`exec_state.transition()` enforces the per-transition role matrix and throws; the shop
floor needs the refusal *recorded* as well (URS-W1-029 AC-3), so every terminal action
goes through here: it delegates to the state machine, and on a permission refusal writes
the audit row before re-raising. The state machine itself is untouched.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.manufacturing_core import exec_state
from rheinwerk_mes.setup.w1_roles import log_transition_refusal


@frappe.whitelist()
def request_transition(work_order: str, target_state: str, reason: str | None = None) -> dict[str, Any]:
	"""Perform an `exec_state` transition from the terminal, auditing any refusal."""
	from_state = frappe.db.get_value("Work Order", work_order, "exec_state") or exec_state.INITIAL_STATE
	try:
		doc = exec_state.transition(work_order, target_state, reason=reason)
	except frappe.PermissionError:
		log_transition_refusal("Work Order", work_order, from_state, target_state)
		raise
	return {"work_order": doc.name, "exec_state": doc.exec_state, "from_state": from_state}
