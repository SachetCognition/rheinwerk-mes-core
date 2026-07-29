"""Legal `exec_state` transition enforcement — TC-W1-002 (URS-W1-002).

The transition set is a pure function over state names, so these run offline like the
characterisation contracts. The document-level path (`Work Order.validate`) is registered in
`hooks.py` and asserted here through the hook registration; its site-backed journey test
arrives with the `exec_state` workflow itself (URS-W1-001, TC-W1-001).
"""

from __future__ import annotations

import pytest

from rheinwerk_mes.execution_gating.order_state import (
	ABANDONED,
	ACCEPTED,
	COMPLETED,
	DECLINED,
	EXEC_STATE_FIELD,
	IN_PROGRESS,
	INTERRUPTED,
	ORDER_STATES,
	PENDING,
	TERMINAL_STATES,
	can_change_to,
	is_terminal,
	legal_targets,
	refusal_message,
	unknown_state_message,
)

LEGAL_PAIRS = (
	(PENDING, ACCEPTED),
	(PENDING, IN_PROGRESS),
	(PENDING, DECLINED),
	(ACCEPTED, IN_PROGRESS),
	(ACCEPTED, DECLINED),
	(IN_PROGRESS, COMPLETED),
	(IN_PROGRESS, INTERRUPTED),
	(IN_PROGRESS, ABANDONED),
	(INTERRUPTED, IN_PROGRESS),
	(INTERRUPTED, ABANDONED),
)


@pytest.mark.parametrize(("source", "target"), LEGAL_PAIRS)
def test_tc_w1_002_legal_transitions_are_permitted(source, target):
	"""TC-W1-002 pass condition: the ten legal transitions stay open."""
	assert can_change_to(source, target) is True


@pytest.mark.parametrize("target", ORDER_STATES)
def test_tc_w1_002_step_2_completed_order_is_terminal(target):
	"""AC-1 · TC-W1-002 step 2: PO-2026-0002 in Completed refuses every transition."""
	assert is_terminal(COMPLETED)
	assert can_change_to(COMPLETED, target) is False


def test_terminal_states_are_completed_declined_and_abandoned():
	"""AC-1: the three terminal states, no more and no fewer."""
	assert TERMINAL_STATES == {COMPLETED, DECLINED, ABANDONED}
	assert legal_targets(COMPLETED) == ()


def test_tc_w1_002_step_1_pending_to_completed_is_refused_naming_the_transition():
	"""AC-2 · TC-W1-002 step 1: PO-2026-0001 in Pending cannot jump to Completed."""
	assert can_change_to(PENDING, COMPLETED) is False
	message = refusal_message(PENDING, COMPLETED)
	assert "Pending → Completed" in message
	assert "Accepted, In Progress, Declined" in message


def test_tc_w1_002_step_3_interrupted_to_completed_is_refused():
	"""TC-W1-002 step 3: an interrupted order must resume before it can complete."""
	assert can_change_to(INTERRUPTED, COMPLETED) is False
	assert legal_targets(INTERRUPTED) == (IN_PROGRESS, ABANDONED)


def test_terminal_refusal_names_the_terminal_state_and_the_way_out():
	"""Gate refusals state which rule, which states and what resolves it (design skill)."""
	message = refusal_message(COMPLETED, IN_PROGRESS)
	assert "Completed ist ein Endzustand" in message
	assert "Completed → In Progress" in message
	assert "neuer Fertigungsauftrag" in message


def test_refusal_message_is_translated_through_the_caller_catalogue():
	"""The template, not the interpolated text, is the translation key (URS-W0-016)."""
	seen: list[str] = []

	def translate(text: str) -> str:
		seen.append(text)
		return text.replace("Übergang", "Transition")

	message = refusal_message(PENDING, COMPLETED, translate)
	assert seen == [
		"Übergang {source} → {target} ist nicht zulässig. Zulässige Übergänge ab {source}: {allowed}."
	]
	assert message.startswith("Transition Pending → Completed")


def test_unknown_exec_state_is_refused():
	"""Parity with `OrderState.parseString`: an unparseable state is an error, not a no-op."""
	with pytest.raises(ValueError, match="unknown exec_state"):
		can_change_to(PENDING, "Closed")
	assert "Closed" in unknown_state_message("Closed")


def test_initial_assignment_has_no_source_state():
	"""A newly created order gets its first `exec_state` without a transition check."""
	assert can_change_to(None, PENDING) is True


def test_gate_is_registered_on_the_work_order_anchor():
	"""The enforcement point is a doc_event on the unforked anchor, not a forked DocType."""
	from rheinwerk_mes import hooks

	assert (
		hooks.doc_events["Work Order"]["validate"]
		== "rheinwerk_mes.execution_gating.order_state_gating.enforce_legal_transition"
	)
	assert EXEC_STATE_FIELD == "exec_state"
