"""TC-W1-006 — how the acceptance gate refuses (rule, record, resolution, log).

Verifies the **URS-W1-005** design conformance clause: the refusal names the rule, the
record and what resolves it (design skill § "Interaction rules — Hard gates look hard"),
dates are German-first, and every refusal is logged. The gate is driven with a
`TransitionContext`-shaped stand-in, so no site is needed; the modal itself is rendered
by the `exec_state` machine, which throws the collected messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

frappe = pytest.importorskip("frappe")

from rheinwerk_mes.execution_gating.acceptance_gate import (  # noqa: E402  (after importorskip)
	ACCEPTED,
	RULE_DATE_RANGE,
	RULE_REQUIRED_FIELDS,
	acceptance_gate,
	refusals,
)


class WorkOrderStub:
	"""The slice of an anchor `Work Order` the gate reads."""

	def __init__(self, name: str, **values: Any) -> None:
		self.name = name
		self._values = values

	def get(self, fieldname: str, default: Any = None) -> Any:
		return self._values.get(fieldname, default)


@dataclass
class TransitionContextStub:
	"""Shaped like `rheinwerk_mes.manufacturing_core.exec_state.TransitionContext`."""

	doc: Any
	from_state: str = "Pending"
	to_state: str = ACCEPTED
	reason: str | None = None
	errors: list[str] = field(default_factory=list)

	def refuse(self, message: str) -> None:
		self.errors.append(message)


def acceptable_order(name: str = "PO-2026-0001", **overrides: Any) -> WorkOrderStub:
	values: dict[str, Any] = {
		"planned_start_date": "10.03.2026",
		"planned_end_date": "12.03.2026",
		"production_line": "LINE-1",
		"bom_no": "BOM-RW-CHM-0003-001",
	}
	values.update(overrides)
	return WorkOrderStub(name, **values)


PLANNER = "p.krueger@rheinwerk-chemie.de"


class LoggerStub:
	"""Collects `warning()` entries; every other logging call is a no-op."""

	def __init__(self, entries: list[Any]) -> None:
		self._entries = entries

	def warning(self, entry: Any) -> None:
		self._entries.append(entry)

	def __getattr__(self, _name: str):
		return lambda *args, **kwargs: None


@pytest.fixture(autouse=True)
def logged(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
	"""Bind an acting user and capture what the gate logs — both need a site otherwise."""
	entries: list[Any] = []
	monkeypatch.setattr(frappe.local, "session", frappe._dict(user=PLANNER), raising=False)
	monkeypatch.setattr(frappe, "logger", lambda *args, **kwargs: LoggerStub(entries))
	return entries


def test_refusal_names_the_rule_the_record_and_the_resolution():
	"""URS-W1-005 AC-1 / TC-W1-006 step 1 — the missing field is named, not hinted at."""
	context = TransitionContextStub(doc=acceptable_order("PO-2026-0002", production_line=None))

	acceptance_gate(context)

	assert len(context.errors) == 1
	message = context.errors[0]
	assert RULE_REQUIRED_FIELDS in message
	assert "PO-2026-0002" in message
	assert "Fertigungslinie" in message
	assert "erneut ausführen" in message


def test_date_range_refusal_cites_both_dates_german_first():
	"""URS-W1-005 AC-2 / TC-W1-006 step 2 — start 15.03.2026, end 14.03.2026."""
	context = TransitionContextStub(
		doc=acceptable_order(
			"PO-2026-0002",
			planned_start_date="2026-03-15 06:00:00",
			planned_end_date="2026-03-14 18:00:00",
		)
	)

	acceptance_gate(context)

	assert len(context.errors) == 1
	message = context.errors[0]
	assert RULE_DATE_RANGE in message
	assert "14.03.2026" in message
	assert "15.03.2026" in message


def test_gate_passes_a_complete_order():
	"""URS-W1-005 AC-3 / TC-W1-006 step 3 — no refusal for PO-2026-0001."""
	context = TransitionContextStub(doc=acceptable_order())

	acceptance_gate(context)

	assert context.errors == []


def test_gate_only_guards_the_acceptance_transition():
	"""URS-W1-005 — other `exec_state` targets have their own gates (URS-W1-007…009)."""
	context = TransitionContextStub(
		doc=acceptable_order("PO-2026-0002", production_line=None),
		from_state="In Progress",
		to_state="Completed",
	)

	acceptance_gate(context)

	assert context.errors == []


def test_every_refusal_is_logged_with_gate_record_and_user(logged: list[Any]):
	"""URS-W1-005 design conformance / TC-W1-036 — compliance moments are logged."""
	context = TransitionContextStub(doc=acceptable_order("PO-2026-0002", production_line=None, bom_no=None))

	acceptance_gate(context)

	assert len(logged) == 1
	entry = logged[0]
	assert entry["work_order"] == "PO-2026-0002"
	assert entry["missing_fields"] == ["production_line", "bom_no"]
	assert entry["inconsistent_date_range"] is False
	assert entry["user"] == PLANNER
	assert entry["to_state"] == ACCEPTED


def test_refusals_are_readable_without_a_transition_context():
	"""URS-W1-005 — sibling W1 children can pre-check an order before offering Accept."""
	assert refusals(acceptable_order()) == []
	assert len(refusals(acceptable_order("PO-2026-0002", planned_end_date=None))) == 1
