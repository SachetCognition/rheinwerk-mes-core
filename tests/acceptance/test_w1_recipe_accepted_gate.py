"""W1-2 — recipe-Accepted acceptance gate (URS-W1-006 · TC-W1-007).

An order may only be accepted against a recipe whose `gov_state` is Accepted (CDM-04 /
ADR-006). The refusal is asserted to be a *raised* hard gate (a modal, never a toast) that
names the rule, the record and the resolution, per the design skill's "Hard gates look
hard", and to name the offending recipe together with its `gov_state`.

Site-backed suite: it skips (never fails) when the Frappe substrate is absent, so the same
`pytest tests` invocation runs offline (contracts only) and on CI's seeded site.
"""

from __future__ import annotations

import pytest

frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

SECOND_ORDER = "PO-2026-0002"
RECIPE = "BOM-RW-CHM-0003-001"
LINE = "LINE-1"
PLANNED_START = "2026-03-10 06:00:00"
PLANNED_END = "2026-03-12 14:00:00"


def _require(site, doctype: str, name: str):
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def _submitted_order(site, name: str = SECOND_ORDER):
	doc = _require(site, "Work Order", name)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	doc.reload()
	site.db.set_value("Work Order", name, "exec_state", exec_state.PENDING, update_modified=False)
	site.db.delete("Order State History", {"parent": name})
	site.db.delete("Execution Gate Log", {"reference_name": name})
	doc.reload()
	return doc


def _set_fields(site, name: str, **values) -> None:
	for fieldname, value in values.items():
		site.db.set_value("Work Order", name, fieldname, value, update_modified=False)


def _set_gov_state(site, recipe: str, state: str) -> None:
	_require(site, "BOM", recipe)
	site.db.set_value("BOM", recipe, "gov_state", state, update_modified=False)


def _arrange_complete_order(site):
	order = _submitted_order(site)
	_set_fields(
		site,
		SECOND_ORDER,
		production_line=LINE,
		planned_start_date=PLANNED_START,
		planned_end_date=PLANNED_END,
	)
	order.reload()
	return order


def _assert_hard_gate(message: str, record: str) -> None:
	"""A hard gate names the rule, the record and the resolution in one raised modal."""
	assert "Regel:" in message, "refusal must name the rule"
	assert "Behebung:" in message, "refusal must name the resolution"
	assert record in message, "refusal must name the record"


def test_acceptance_refused_while_recipe_is_draft(site):
	"""AC-1 — a Draft recipe blocks acceptance of PO-2026-0002, naming recipe and gov_state."""
	order = _arrange_complete_order(site)
	_set_gov_state(site, RECIPE, "Draft")

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.ACCEPTED)

	message = str(excinfo.value)
	_assert_hard_gate(message, SECOND_ORDER)
	assert RECIPE in message and "Draft" in message
	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.PENDING


def test_recipe_gate_refusal_is_logged(site):
	"""URS-W1-033 — the recipe gate's refusal writes an immutable audit row."""
	order = _arrange_complete_order(site)
	_set_gov_state(site, RECIPE, "Draft")

	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)

	entries = audit.entries_for("Work Order", SECOND_ORDER)
	assert [entry for entry in entries if entry["gate"] == "recipe_accepted_gate"]


def test_acceptance_succeeds_after_recipe_is_accepted(site):
	"""AC-2 — once the recipe moves to Accepted (URS-W1-015), the retry succeeds."""
	order = _arrange_complete_order(site)
	_set_gov_state(site, RECIPE, "Draft")
	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)

	_set_gov_state(site, RECIPE, "Accepted")
	order.reload()
	exec_state.transition(order, exec_state.ACCEPTED)

	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.ACCEPTED


def test_recipe_gate_is_registered_after_acceptance_gate(site):
	"""The recipe gate runs on * → Accepted, after the acceptance-fields gate."""
	registered = frappe.get_hooks(exec_state.GATE_HOOK)
	acceptance = "rheinwerk_mes.execution_gating.gates.acceptance_gate"
	recipe = "rheinwerk_mes.execution_gating.gates.recipe_accepted_gate"
	assert acceptance in registered and recipe in registered
	assert registered.index(recipe) > registered.index(acceptance)
