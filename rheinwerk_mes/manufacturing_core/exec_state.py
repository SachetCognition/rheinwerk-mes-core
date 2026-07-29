"""Production-order `exec_state` change audit (URS-W1-003).

Every `exec_state` change on the anchor Work Order — from the Desk, from
`transition()` or from any server-side caller — funnels through
`record_exec_state_change()`, which

1. refuses the change when a reason is mandatory and missing
   (Declined / Abandoned / Interrupted),
2. appends one `state_history` row carrying state, user, timestamp and reason.

The anchor is never forked: `exec_state`, `exec_state_reason` and `state_history`
are Custom Fields owned by `rheinwerk_mes` (`rheinwerk_mes.setup.w1_state_audit`).
Transition legality (URS-W1-002), the Frappe workflow and role gating
(URS-W1-001) are separate deliverables layered on this funnel.

Legacy baseline (semantics only, never ported) — Qcadoo
`orders/model/orderStateChange.xml:36-47` (audit row) and
`orders/model/reasonTypeOfChangingOrderState.xml` (mandatory reason states).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

PENDING = "Pending"
ACCEPTED = "Accepted"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
INTERRUPTED = "Interrupted"
ABANDONED = "Abandoned"
DECLINED = "Declined"

#: Initial state of every production order (Qcadoo `OrderState.PENDING`).
INITIAL_STATE = PENDING

#: The `exec_state` vocabulary, in workflow order (glossary spelling is law).
STATES: tuple[str, ...] = (
	PENDING,
	ACCEPTED,
	IN_PROGRESS,
	COMPLETED,
	INTERRUPTED,
	ABANDONED,
	DECLINED,
)

#: Qcadoo `reasonTypeOfChangingOrderState.xml` — a reason is mandatory for these targets.
REASON_REQUIRED_STATES: frozenset[str] = frozenset({DECLINED, ABANDONED, INTERRUPTED})

HISTORY_FIELD = "state_history"
STATE_FIELD = "exec_state"
REASON_FIELD = "exec_state_reason"


def requires_reason(to_state: str | None) -> bool:
	"""True when a change into `to_state` may not be recorded without a reason."""
	return to_state in REASON_REQUIRED_STATES


def is_reason_satisfied(to_state: str | None, reason: str | None) -> bool:
	"""True when `reason` meets the mandatory-reason rule for `to_state`."""
	if not requires_reason(to_state):
		return True
	return bool((reason or "").strip())


def build_history_row(
	from_state: str | None,
	to_state: str,
	changed_by: str,
	changed_at: Any,
	reason: str | None = None,
) -> dict[str, Any]:
	"""The audit row written for one `exec_state` change."""
	return {
		"from_state": from_state or None,
		"to_state": to_state,
		"changed_by": changed_by,
		"changed_at": changed_at,
		"reason": (reason or "").strip() or None,
	}


def _stored_state(doc: Any) -> str:
	return frappe.db.get_value("Work Order", doc.name, STATE_FIELD) or INITIAL_STATE


def _reason_of(doc: Any) -> str | None:
	return doc.flags.get("exec_state_reason") or doc.get(REASON_FIELD)


def set_default_exec_state(doc: Any, method: str | None = None) -> None:
	"""`Work Order.before_insert` — a new production order starts in Pending."""
	if not doc.get(STATE_FIELD):
		doc.set(STATE_FIELD, INITIAL_STATE)


def record_exec_state_change(doc: Any, method: str | None = None) -> None:
	"""`Work Order.validate` / `on_update_after_submit` — audit one state change.

	Refuses the change when the target state demands a reason and none was given
	(URS-W1-003 AC-2), otherwise appends the `state_history` row (AC-1).
	"""
	if not doc.meta.has_field(STATE_FIELD) or not doc.meta.has_field(HISTORY_FIELD):
		return
	if doc.get("__islocal") or not frappe.db.exists("Work Order", doc.name):
		set_default_exec_state(doc)
		return

	from_state = _stored_state(doc)
	to_state = doc.get(STATE_FIELD) or INITIAL_STATE
	if to_state == from_state:
		return

	reason = _reason_of(doc)
	if not is_reason_satisfied(to_state, reason):
		frappe.throw(
			_("Für den Zustand {0} ist eine Begründung erforderlich (Auftrag {1}).").format(
				_(to_state), doc.name
			),
			title=_("Übergang abgelehnt: {0} → {1}").format(_(from_state), _(to_state)),
		)

	doc.append(
		HISTORY_FIELD,
		build_history_row(from_state, to_state, frappe.session.user, now_datetime(), reason),
	)


@frappe.whitelist()
def transition(work_order: Any, target_state: str, reason: str | None = None) -> Any:
	"""Move a production order to `target_state`, recording the audit row.

	Raises `frappe.ValidationError` when the target state demands a reason and none
	was supplied.
	"""
	doc = frappe.get_doc("Work Order", work_order) if isinstance(work_order, str) else work_order
	doc.flags.exec_state_reason = reason
	doc.set(STATE_FIELD, target_state)
	if doc.meta.has_field(REASON_FIELD):
		doc.set(REASON_FIELD, reason)
	doc.save()
	return doc


def state_history(work_order: str) -> list[dict[str, Any]]:
	"""Audit rows of `work_order`, oldest first."""
	doc = frappe.get_doc("Work Order", work_order)
	return [
		{
			"from_state": row.from_state,
			"to_state": row.to_state,
			"changed_by": row.changed_by,
			"changed_at": row.changed_at,
			"reason": row.reason,
		}
		for row in doc.get(HISTORY_FIELD) or []
	]
