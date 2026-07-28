"""TC-W1-002 — legal transitions only, exact Qcadoo `canChangeTo` parity.

Verifies **URS-W1-002** through **TC-W1-002** of `docs/test/TST-W1-production-core.md`,
including the parity assertion of the W0 characterisation harness (TC-W1-030 row P-1:
"Order transition legality (7-state `canChangeTo`)").

Legacy baseline re-expressed here (semantics only, never ported) from
`SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/constants/
OrderState.java:31-81`.
"""

from __future__ import annotations

import itertools

import pytest
from test_w1_exec_state_support import (
	PLANNER_USER,
	force_state,
	submitted_order,
)

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")


#: `OrderState.canChangeTo` transcribed state by state from `OrderState.java:31-81`.
QCADOO_CAN_CHANGE_TO: dict[str, set[str]] = {
	"Pending": {"Accepted", "In Progress", "Declined"},  # :33-38
	"Accepted": {"In Progress", "Declined"},  # :39-45
	"In Progress": {"Completed", "Interrupted", "Abandoned"},  # :46-52
	"Completed": set(),  # :53-59  canChangeTo -> false
	"Declined": set(),  # :60-66  canChangeTo -> false
	"Interrupted": {"Abandoned", "In Progress"},  # :67-73
	"Abandoned": set(),  # :74-80  canChangeTo -> false
}


def test_transition_table_matches_qcadoo_can_change_to():
	"""URS-W1-002 / TC-W1-002 — the implemented table is the legacy table, exactly."""
	implemented = {state: set(targets) for state, targets in exec_state.LEGAL_TRANSITIONS.items()}
	assert implemented == QCADOO_CAN_CHANGE_TO
	assert set(exec_state.STATES) == set(QCADOO_CAN_CHANGE_TO)
	assert exec_state.TERMINAL_STATES == {"Completed", "Declined", "Abandoned"}


@pytest.mark.parametrize(
	("from_state", "to_state"),
	list(itertools.product(QCADOO_CAN_CHANGE_TO, QCADOO_CAN_CHANGE_TO)),
)
def test_every_state_pair_matches_the_legacy_verdict(from_state, to_state):
	"""URS-W1-002 / TC-W1-002 — all 49 ordered pairs judged as Qcadoo judges them."""
	assert exec_state.is_legal(from_state, to_state) is (to_state in QCADOO_CAN_CHANGE_TO[from_state])


def test_characterisation_harness_still_passes_against_the_implementation():
	"""URS-W1-002 AC-3 / TC-W1-002 step 4 (TC-W1-030) — harness parity, no drift."""
	import sys
	from pathlib import Path

	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
	from characterisation.registry import all_contracts

	contracts = all_contracts()
	assert contracts, "characterisation registry is empty"
	for contract in contracts:
		for case in contract.cases():
			if (
				contract.divergence
				and case.get("diverges")
				and contract.resolution().is_target_implementation
			):
				# A signed-off divergence (URS-W1-030) must *not* match the legacy verdict;
				# the behaviour record proves it instead (tools/behaviour).
				with pytest.raises(AssertionError):
					contract.check(case)
				continue
			contract.check(case)


def test_direct_jump_pending_to_completed_is_refused(site):
	"""URS-W1-002 AC-2 / TC-W1-002 step 1 — refusal names the illegal transition."""
	order = submitted_order(site, "PO-2026-0002")
	site.set_user(PLANNER_USER)
	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order.name, exec_state.COMPLETED)
	message = str(excinfo.value)
	assert "Pending" in message and "Completed" in message


def test_terminal_states_refuse_every_transition(site):
	"""URS-W1-002 AC-1 / TC-W1-002 step 2 — Completed/Declined/Abandoned are terminal."""
	order = submitted_order(site)
	for terminal in sorted(exec_state.TERMINAL_STATES):
		for target in exec_state.STATES:
			if target == terminal:
				continue
			force_state(site, order, terminal)
			with pytest.raises(frappe.ValidationError):
				exec_state.transition(order.name, target, reason="Test")


def test_interrupted_cannot_complete(site):
	"""URS-W1-002 / TC-W1-002 step 3 — Interrupted→Completed is not in `canChangeTo`."""
	order = force_state(site, submitted_order(site), exec_state.INTERRUPTED)
	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order.name, exec_state.COMPLETED)
