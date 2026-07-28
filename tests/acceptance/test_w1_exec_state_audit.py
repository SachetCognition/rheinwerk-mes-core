"""TC-W1-003 — `state_history` audit rows and mandatory reasons.

Verifies **URS-W1-003** through **TC-W1-003** of `docs/test/TST-W1-production-core.md`.
Legacy baseline (semantics only): `orders/model/orderStateChange.xml:36-47` and
`orders/model/reasonTypeOfChangingOrderState.xml` in `SachetCognition/Chem_mes@master`.
"""

from __future__ import annotations

import pytest
from test_w1_exec_state_support import (
	OPERATOR_USER,
	PLANNER_USER,
	force_state,
	submitted_order,
)

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")


def test_history_records_state_user_and_timestamp(site):
	"""URS-W1-003 AC-1 / TC-W1-003 step 1 — two rows, right users, ascending times."""
	order = submitted_order(site)

	site.set_user(PLANNER_USER)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	site.set_user(OPERATOR_USER)
	exec_state.transition(order.name, exec_state.IN_PROGRESS)

	site.set_user("Administrator")
	rows = exec_state.state_history(order.name)
	assert [(row["from_state"], row["to_state"]) for row in rows] == [
		(exec_state.PENDING, exec_state.ACCEPTED),
		(exec_state.ACCEPTED, exec_state.IN_PROGRESS),
	]
	assert [row["changed_by"] for row in rows] == [PLANNER_USER, OPERATOR_USER]
	assert rows[0]["changed_at"] <= rows[1]["changed_at"]


@pytest.mark.parametrize("target", sorted(exec_state.REASON_REQUIRED_STATES))
def test_reason_is_mandatory_for_declined_abandoned_interrupted(site, target):
	"""URS-W1-003 AC-2 / TC-W1-003 step 2 — reason-required targets refuse without one."""
	order = submitted_order(site, "PO-2026-0002")
	source = exec_state.PENDING if target == exec_state.DECLINED else exec_state.IN_PROGRESS
	force_state(site, order, source)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order.name, target)
	assert "Begründung" in str(excinfo.value)

	exec_state.transition(order.name, target, reason="Kunde storniert")
	rows = exec_state.state_history(order.name)
	assert rows[-1]["to_state"] == target
	assert rows[-1]["reason"] == "Kunde storniert"


def test_reasonless_transitions_store_no_reason(site):
	"""URS-W1-003 / TC-W1-003 — Accept needs no reason and stores none."""
	order = submitted_order(site)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	assert exec_state.state_history(order.name)[-1]["reason"] is None
