"""Completion gate: recorded output > 0 — URS-W1-007, TC-W1-008, TC-W1-030.

Baseline (`SachetCognition/Chem_mes@master`):
`OrderStateValidationService.java:54-63` (`validationOnCompleted`) with `checkRequired`
at `:64-72`.

The parity cases below are the committed cases of the W0 characterisation contract
`CHAR-ORDER-COMPLETE-01` (URS-W0-012 AC-2). Once that harness is on the branch, the same
cases run through `tests/characterisation/api.py::ENTRYPOINTS["order_completion"]`, which
points at `evaluate_order_completion` here — the assertions in this module keep the
entrypoint honest on its own.
"""

from __future__ import annotations

from typing import Any

import pytest

from rheinwerk_mes.execution_gating.contracts import (
	DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO,
	FIELD_REQUIRED,
	evaluate_order_completion,
)

pytest.importorskip("frappe", reason="the gate adapter runs inside a Frappe app")

from rheinwerk_mes.execution_gating import gates  # noqa: E402  (needs frappe importable)

#: `CHAR-ORDER-COMPLETE-01` fixture cases: (id, order, allowed, errors).
PARITY_CASES = [
	(
		"COMPLETE-01-done-quantity-zero",
		{"date_from": "02.02.2026", "date_to": "06.02.2026", "done_quantity": 0},
		False,
		(DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO,),
	),
	(
		"COMPLETE-02-done-quantity-positive",
		{"date_from": "02.02.2026", "date_to": "06.02.2026", "done_quantity": 480},
		True,
		(),
	),
	(
		"COMPLETE-03-done-quantity-null",
		{"date_from": "02.02.2026", "date_to": "06.02.2026", "done_quantity": None},
		False,
		(FIELD_REQUIRED,),
	),
	(
		"COMPLETE-04-date-to-missing-and-zero-quantity",
		{"date_from": "02.02.2026", "date_to": None, "done_quantity": 0},
		False,
		(FIELD_REQUIRED, DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO),
	),
]


class FakeOrder:
	"""Minimal stand-in for the anchor `Work Order` document (site-free)."""

	def __init__(self, before: FakeOrder | None = None, **values: Any) -> None:
		self._values = values
		self._before = before

	def get(self, fieldname: str) -> Any:
		return self._values.get(fieldname)

	def get_doc_before_save(self) -> FakeOrder | None:
		return self._before


#: PO-2026-0001 as the TC-W1-008 fixture holds it, In Progress with nothing recorded.
PO_2026_0001: dict[str, Any] = {
	"name": "PO-2026-0001",
	"status": "In Process",
	"planned_start_date": "02.02.2026",
	"planned_end_date": "06.02.2026",
	"qty": 500,
	"produced_qty": 0,
}


def in_progress_order(**overrides: Any) -> FakeOrder:
	"""The order before the completion attempt."""
	return FakeOrder(**{**PO_2026_0001, **overrides})


def completing_order(**overrides: Any) -> FakeOrder:
	"""The same order on the save that moves it into Completed."""
	return FakeOrder(before=in_progress_order(), **{**PO_2026_0001, "status": "Completed", **overrides})


@pytest.mark.parametrize(
	("order", "allowed", "errors"),
	[case[1:] for case in PARITY_CASES],
	ids=[case[0] for case in PARITY_CASES],
)
def test_completion_contract_matches_the_legacy_verdict(order, allowed, errors):
	"""URS-W1-007 AC-3 · TC-W1-030 — the target entrypoint reproduces Qcadoo verbatim."""
	verdict = evaluate_order_completion(order)
	assert verdict.allowed is allowed
	assert verdict.errors == errors


def test_zero_recorded_output_is_refused_citing_the_output():
	"""URS-W1-007 AC-1 · TC-W1-008 step 1 — refusal modal names rule, record, resolution."""
	refusals = gates.completion_refusals(completing_order(produced_qty=0))
	assert [refusal.gate for refusal in refusals] == ["completion_gate"]
	refusal = refusals[0]
	assert "erfasste Ausbringung" in refusal.rule
	assert "PO-2026-0001 — erfasste Ausbringung 0 kg von 500 kg" in refusal.record
	assert refusal.resolution
	message = refusal.as_message()
	assert "<b>Regel:</b>" in message
	assert "<b>Datensatz:</b>" in message
	assert "<b>Behebung:</b>" in message


def test_recorded_output_of_500_kg_completes():
	"""URS-W1-007 AC-2 · TC-W1-008 step 2 — the gate passes once output is recorded."""
	doc = completing_order(produced_qty=500)
	assert gates.completion_refusals(doc) == ()
	gates.completion_gate(doc)  # no refusal is raised


def test_missing_execution_date_is_refused_separately():
	"""URS-W1-007 — the required-field refusal names the missing German-first label."""
	refusals = gates.completion_refusals(completing_order(planned_end_date=None, produced_qty=250))
	assert len(refusals) == 1
	assert "Geplanter Endtermin" in refusals[0].record


def test_missing_date_and_zero_output_are_both_reported():
	"""URS-W1-007 — refusals accumulate, required-field first (legacy evaluation order)."""
	refusals = gates.completion_refusals(completing_order(planned_end_date=None, produced_qty=0))
	assert len(refusals) == 2
	assert "Geplanter Endtermin" in refusals[0].record
	assert "erfasste Ausbringung" in refusals[1].rule


def test_gate_only_fires_on_the_transition_into_completed():
	"""URS-W1-007 · URS-W1-004 — other saves and re-saves of a completed order pass through."""
	assert not gates.entering_completed(in_progress_order())
	already_completed = FakeOrder(
		before=FakeOrder(name="PO-2026-0001", status="Completed"),
		name="PO-2026-0001",
		status="Completed",
		produced_qty=0,
	)
	assert not gates.entering_completed(already_completed)
	assert gates.entering_completed(completing_order())


def test_exec_state_takes_precedence_over_the_anchor_status():
	"""URS-W1-004 — when the W1 workflow is installed the gate reads `exec_state`."""
	doc = FakeOrder(
		before=FakeOrder(name="PO-2026-0001", exec_state="In Progress", status="In Process"),
		name="PO-2026-0001",
		exec_state="Completed",
		status="In Process",
		planned_start_date="02.02.2026",
		planned_end_date="06.02.2026",
		qty=500,
		produced_qty=0,
	)
	assert gates.entering_completed(doc)
	assert gates.completion_refusals(doc)


def test_recorded_output_is_rendered_german_first():
	"""URS-W1-034 — decimal comma and kg unit in gate texts."""
	assert gates.kg(480.5) == "480,5 kg"
	assert gates.kg(0) == "0 kg"
	assert gates.kg(None) == "0 kg"
