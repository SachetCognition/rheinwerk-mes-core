"""Post-transition side effects of a gated order transition (W1-2).

Gates judge, they never post (`docs/design/W1-exec-state.md` §4), so the effects that
*follow* a written transition live here and hang off the anchor `Work Order` document
events.

* **URS-W1-009** — the reservations held by an order are released when it reaches Declined
  or Abandoned. Legacy baseline `OrderStatesListenerServicePFTD.clearReservations`
  (:129-131), wired by `OrderStatesListenerAspectPFTD:68-81` for the transitions into
  *abandoned* and *declined* (`SachetCognition/Chem_mes@master`); the release itself is the
  warehouse module's API `warehouse.reservations.release_for_order` (URS-W1-025).

The effect is keyed on the `state_history` row the state machine (URS-W1-001) appends for
the transition and is idempotent: the underlying release finds nothing to do on a repeated
save, so acting once or many times has the same result.
"""

from __future__ import annotations

from typing import Any

DECLINED = "Declined"
ABANDONED = "Abandoned"

#: Terminal states that free the order's reserved stock (Qcadoo `clearReservations`).
RESERVATION_CLEARING_STATES: frozenset[str] = frozenset({DECLINED, ABANDONED})


def on_work_order_update(doc: Any, method: str | None = None) -> None:
	"""`Work Order.on_update` / `on_update_after_submit` — react to a written transition.

	Only the transition just recorded in `state_history` is acted on; if the order has
	moved into Declined or Abandoned, its reservations are released (URS-W1-009).
	"""
	row = _latest_history_row(doc)
	if not row or row.to_state != doc.get("exec_state"):
		return
	if row.to_state in RESERVATION_CLEARING_STATES:
		release_order_reservations(doc.name)


def release_order_reservations(work_order: str) -> int:
	"""Release every reservation the order holds (URS-W1-009); returns the count released."""
	from rheinwerk_mes.warehouse.reservations import release_for_order

	return release_for_order(work_order)


def _latest_history_row(doc: Any) -> Any:
	rows = doc.get("state_history") or []
	return rows[-1] if rows else None
