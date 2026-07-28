"""Post-transition side effects of a gated order transition (W1-2).

Gates judge, they never post (`docs/design/W1-exec-state.md` §4), so the two effects that
*follow* a written transition live here and hang off the anchor `Work Order` document
events:

* **URS-W1-009** — reservations held by an order are released when it reaches Declined or
  Abandoned. Legacy baseline `OrderStatesListenerServicePFTD.clearReservations` (:129-131),
  wired by `OrderStatesListenerAspectPFTD:68-81` for the transitions into *abandoned* and
  *declined* (`SachetCognition/Chem_mes@master`); the release itself is the warehouse
  module's API `warehouse.reservations.release_for_order` (URS-W1-025).
* **URS-W1-033** — the executed transition is written to the immutable
  `Execution Gate Log`, so the audit view shows refusals *and* transitions.

Both are keyed on the `state_history` row the state machine just appended, and are
idempotent: a row is acted on once, whatever else saves the document afterwards.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.execution_gating import audit

DECLINED = "Declined"
ABANDONED = "Abandoned"

#: Terminal states that free the order's reserved stock (Qcadoo `clearReservations`).
RESERVATION_CLEARING_STATES: frozenset[str] = frozenset({DECLINED, ABANDONED})

TRANSITION_GATE = "exec_state_transition"


def on_work_order_update(doc: Any, method: str | None = None) -> None:
	"""`Work Order.on_update` / `on_update_after_submit` — react to a written transition."""
	row = _latest_history_row(doc)
	if not row or row.to_state != doc.get("exec_state"):
		return
	if _already_processed(doc.name, row.name):
		return

	audit.log_transition(
		gate=TRANSITION_GATE,
		rule=_("Zustandswechsel des Fertigungsauftrags wurde nach Prüfung aller Gates ausgeführt."),
		document=doc,
		from_state=row.from_state,
		to_state=row.to_state,
		detail=row.reason or None,
		state_history_row=row.name,
	)

	if row.to_state in RESERVATION_CLEARING_STATES:
		release_order_reservations(doc.name)


def release_order_reservations(work_order: str) -> int:
	"""Release every reservation the order holds (URS-W1-009); returns the count released."""
	from rheinwerk_mes.warehouse.reservations import release_for_order

	return release_for_order(work_order)


def _latest_history_row(doc: Any) -> Any:
	rows = doc.get("state_history") or []
	return rows[-1] if rows else None


def _already_processed(work_order: str, state_history_row: str) -> bool:
	return bool(
		frappe.db.exists(
			audit.LOG_DOCTYPE,
			{
				"reference_doctype": "Work Order",
				"reference_name": work_order,
				"state_history_row": state_history_row,
			},
		)
	)
