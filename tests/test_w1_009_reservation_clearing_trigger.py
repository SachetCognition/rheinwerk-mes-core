"""Offline unit checks for the URS-W1-009 reservation-clearing side effect.

These exercise the decision logic of
`execution_gating.side_effects.on_work_order_update` without a Frappe site: the release
itself is stubbed, so the assertions are purely about *when* an order's reservations are
released. The end-to-end behaviour against real Stock Reservation Entries is covered by the
site-backed TC-W1-010 in `tests/acceptance/test_w1_reservation_clearing.py`.
"""

from __future__ import annotations

from rheinwerk_mes.execution_gating import side_effects


class _HistoryRow:
	def __init__(self, to_state: str):
		self.to_state = to_state


class _FakeWorkOrder:
	def __init__(self, name: str, exec_state: str | None, history: list[_HistoryRow]):
		self.name = name
		self._values = {"exec_state": exec_state, "state_history": history}

	def get(self, key):
		return self._values.get(key)


def _record_releases(monkeypatch) -> list[str]:
	released: list[str] = []
	monkeypatch.setattr(
		side_effects,
		"release_order_reservations",
		lambda work_order: released.append(work_order),
	)
	return released


def test_release_fires_on_transition_into_declined(monkeypatch):
	released = _record_releases(monkeypatch)
	doc = _FakeWorkOrder("PO-2026-0002", "Declined", [_HistoryRow("Accepted"), _HistoryRow("Declined")])

	side_effects.on_work_order_update(doc)

	assert released == ["PO-2026-0002"]


def test_release_fires_on_transition_into_abandoned(monkeypatch):
	released = _record_releases(monkeypatch)
	doc = _FakeWorkOrder(
		"PO-2026-0003",
		"Abandoned",
		[_HistoryRow("In Progress"), _HistoryRow("Abandoned")],
	)

	side_effects.on_work_order_update(doc)

	assert released == ["PO-2026-0003"]


def test_release_does_not_fire_on_non_clearing_transition(monkeypatch):
	released = _record_releases(monkeypatch)
	doc = _FakeWorkOrder("PO-2026-0004", "Accepted", [_HistoryRow("Pending"), _HistoryRow("Accepted")])

	side_effects.on_work_order_update(doc)

	assert released == []


def test_release_does_not_fire_without_a_recorded_transition(monkeypatch):
	released = _record_releases(monkeypatch)
	doc = _FakeWorkOrder("PO-2026-0005", "Declined", [])

	side_effects.on_work_order_update(doc)

	assert released == []


def test_release_ignores_stale_exec_state(monkeypatch):
	"""A save that did not record the current state (no new transition) is a no-op."""
	released = _record_releases(monkeypatch)
	doc = _FakeWorkOrder("PO-2026-0006", "In Progress", [_HistoryRow("Declined")])

	side_effects.on_work_order_update(doc)

	assert released == []
