"""W1-2 — execution-gating hooks on the production-order state machine.

Covers TC-W1-006 (URS-W1-005 acceptance gate), TC-W1-007 (URS-W1-006 recipe-Accepted
gate), TC-W1-008 (URS-W1-007 completion gate), TC-W1-009 (URS-W1-008 material-availability
hard gate) and TC-W1-010 (URS-W1-009 reservations released on Declined/Abandoned).

Every refusal is asserted to be a *raised* hard gate (a modal, never a toast) that names
the rule, the record and the resolution, per the design skill's "Hard gates look hard".
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
gates = pytest.importorskip("rheinwerk_mes.execution_gating.gates")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
availability = pytest.importorskip("rheinwerk_mes.warehouse.availability")
reservations = pytest.importorskip("rheinwerk_mes.warehouse.reservations")

from test_w1_gating_support import (  # noqa: E402  (import after the substrate check)
	COMPONENT_A,
	COMPONENT_B,
	FIRST_ORDER,
	LINE,
	RECIPE,
	RM_WAREHOUSE,
	SECOND_ORDER,
	force_state,
	set_fields,
	set_governance_state,
	stock_ledger_count,
	submitted_order,
)

PLANNED_START = "2026-03-10 06:00:00"
PLANNED_END = "2026-03-12 14:00:00"


def _refusal(excinfo) -> str:
	return str(excinfo.value)


def _assert_hard_gate(message: str, record: str) -> None:
	"""A hard gate names the rule, the record and the resolution in one raised modal."""
	assert "Regel:" in message, "refusal must name the rule"
	assert "Behebung:" in message, "refusal must name the resolution"
	assert record in message, "refusal must name the record"


# --------------------------------------------------------------------------------------
# TC-W1-006 — acceptance gate (URS-W1-005)
# --------------------------------------------------------------------------------------


def test_acceptance_refused_without_production_line(site):
	"""URS-W1-005 · TC-W1-006 step 1 — missing `production_line` refuses acceptance."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(site, order, production_line=None, planned_end_date=PLANNED_END)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.ACCEPTED)

	message = _refusal(excinfo)
	_assert_hard_gate(message, SECOND_ORDER)
	assert "Fertigungslinie" in message
	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.PENDING


def test_acceptance_refused_when_end_date_not_after_start(site):
	"""URS-W1-005 · TC-W1-006 step 2 — end 14.03.2026 before start 15.03.2026 is refused."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date="2026-03-15 06:00:00",
		planned_end_date="2026-03-14 06:00:00",
	)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.ACCEPTED)

	message = _refusal(excinfo)
	_assert_hard_gate(message, SECOND_ORDER)
	assert "Endtermin muss nach dem Starttermin" in message
	assert "15.03.2026" in message and "14.03.2026" in message, "dates rendered DD.MM.YYYY"


def test_acceptance_succeeds_once_dates_line_and_recipe_are_complete(site):
	"""URS-W1-005 · TC-W1-006 step 3 — complete order with an Accepted recipe is accepted."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date=PLANNED_START,
		planned_end_date=PLANNED_END,
	)
	set_governance_state(site, RECIPE, "Accepted")

	exec_state.transition(order, exec_state.ACCEPTED)

	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.ACCEPTED


def test_acceptance_gate_is_side_effect_free(site):
	"""URS-W1-005 · TC-W1-006 — a refused acceptance posts nothing to the ledger."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(site, order, production_line=None)
	before = stock_ledger_count(site)

	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)

	assert stock_ledger_count(site) == before


# --------------------------------------------------------------------------------------
# TC-W1-007 — recipe-Accepted gate (URS-W1-006)
# --------------------------------------------------------------------------------------


def test_acceptance_refused_while_recipe_governance_is_draft(site):
	"""URS-W1-006 · TC-W1-007 step 1 — a Draft recipe blocks acceptance, naming `gov_state`."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date=PLANNED_START,
		planned_end_date=PLANNED_END,
	)
	set_governance_state(site, RECIPE, "Draft")

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.ACCEPTED)

	message = _refusal(excinfo)
	_assert_hard_gate(message, SECOND_ORDER)
	assert RECIPE in message and "Draft" in message
	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.PENDING


def test_acceptance_succeeds_after_recipe_is_accepted(site):
	"""URS-W1-006 · TC-W1-007 step 2 — the retry succeeds once governance is Accepted."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date=PLANNED_START,
		planned_end_date=PLANNED_END,
	)
	set_governance_state(site, RECIPE, "Draft")
	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)

	set_governance_state(site, RECIPE, "Accepted")
	order.reload()
	exec_state.transition(order, exec_state.ACCEPTED)

	assert site.db.get_value("Work Order", SECOND_ORDER, "exec_state") == exec_state.ACCEPTED


# --------------------------------------------------------------------------------------
# TC-W1-008 — completion gate (URS-W1-007)
# --------------------------------------------------------------------------------------


def test_completion_refused_with_zero_recorded_output(site):
	"""URS-W1-007 · TC-W1-008 step 1 — completing at 0 kg output is refused in kg wording."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.IN_PROGRESS)
	set_fields(site, order, planned_end_date=PLANNED_END, produced_qty=0)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.COMPLETED)

	message = _refusal(excinfo)
	_assert_hard_gate(message, FIRST_ORDER)
	assert "Ausbringung" in message and "kg" in message
	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.IN_PROGRESS


def test_completion_refused_without_execution_dates(site):
	"""URS-W1-007 · TC-W1-008 — a missing planned end date refuses completion as well."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.IN_PROGRESS)
	set_fields(site, order, planned_end_date=None, produced_qty=500)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.COMPLETED)

	assert "Geplanter Endtermin" in _refusal(excinfo)


def test_completion_succeeds_with_full_output(site):
	"""URS-W1-007 · TC-W1-008 step 2 — 500 kg recorded output completes the order."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.IN_PROGRESS)
	set_fields(site, order, planned_end_date=PLANNED_END, produced_qty=500)

	exec_state.transition(order, exec_state.COMPLETED)

	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.COMPLETED


# --------------------------------------------------------------------------------------
# TC-W1-009 — material-availability hard gate (URS-W1-008)
# --------------------------------------------------------------------------------------


def test_start_refused_with_per_component_shortfall_list(site):
	"""URS-W1-008 · TC-W1-009 steps 1+3 — reservations of another order create the shortfall.

	The second order reserves 160 kg RW-CHM-0001 and 40 kg RW-CHM-0002; the first order then
	sees 390 kg / 60 kg available against 400 kg / 100 kg required, i.e. exactly the
	per-component shortfalls the refusal must list — proving reserved stock is excluded from
	availability (AC-3).
	"""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.ACCEPTED)
	other = submitted_order(site, SECOND_ORDER)
	assert reservations.reserve_for_order(other.name) > 0

	shortfalls = gates.component_shortfalls(order)
	by_item = {row["item"]: row for row in shortfalls}
	assert set(by_item) == {COMPONENT_A, COMPONENT_B}
	assert float(by_item[COMPONENT_A]["shortfall"]) == pytest.approx(10.0)
	assert float(by_item[COMPONENT_B]["shortfall"]) == pytest.approx(40.0)

	before = stock_ledger_count(site)
	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order, exec_state.IN_PROGRESS)

	message = _refusal(excinfo)
	_assert_hard_gate(message, FIRST_ORDER)
	assert "Fehlmenge 10 kg" in message and "Fehlmenge 40 kg" in message
	assert COMPONENT_A in message and COMPONENT_B in message
	assert stock_ledger_count(site) == before, "the gate must not post anything"
	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.ACCEPTED


def test_start_succeeds_once_stock_is_no_longer_reserved(site):
	"""URS-W1-008 · TC-W1-009 step 2 — releasing the competing reservation lets the order start."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.ACCEPTED)
	other = submitted_order(site, SECOND_ORDER)
	reservations.reserve_for_order(other.name)
	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.IN_PROGRESS)

	reservations.release_for_order(other.name)
	order.reload()
	exec_state.transition(order, exec_state.IN_PROGRESS)

	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.IN_PROGRESS


def test_availability_ignores_the_orders_own_reservation(site):
	"""URS-W1-008 · TC-W1-009 — an order does not block on stock it reserved for itself."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.ACCEPTED)
	reservations.reserve_for_order(order.name)
	assert availability.reserved_qty(COMPONENT_A, RM_WAREHOUSE) > 0

	# The order's own reservation is added back; other vouchers' reservations are not.
	assert gates.component_shortfalls(order) == []

	exec_state.transition(order, exec_state.IN_PROGRESS)
	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.IN_PROGRESS


# --------------------------------------------------------------------------------------
# TC-W1-010 — reservations released on Declined / Abandoned (URS-W1-009)
# --------------------------------------------------------------------------------------


def test_declining_an_order_releases_its_reservations(site):
	"""URS-W1-009 · TC-W1-010 — declining releases the SREs and restores available quantity."""
	order = submitted_order(site, SECOND_ORDER)
	reservations.reserve_for_order(order.name)
	reserved_before = availability.available_qty(COMPONENT_B, RM_WAREHOUSE)

	exec_state.transition(order, exec_state.DECLINED, reason="Kundenstorno")

	live = site.get_all(
		"Stock Reservation Entry",
		filters={"voucher_no": order.name, "docstatus": ["<", 2], "status": ["!=", "Cancelled"]},
	)
	assert live == [], "no live reservation may survive a declined order"
	assert availability.available_qty(COMPONENT_B, RM_WAREHOUSE) > reserved_before


def test_abandoning_an_order_releases_its_reservations(site):
	"""URS-W1-009 · TC-W1-010 — the same release fires on Abandoned, and stays idempotent."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.IN_PROGRESS)
	reservations.reserve_for_order(order.name)

	exec_state.transition(order, exec_state.ABANDONED, reason="Anlagenschaden")

	assert (
		site.get_all(
			"Stock Reservation Entry",
			filters={"voucher_no": order.name, "docstatus": ["<", 2], "status": ["!=", "Cancelled"]},
		)
		== []
	)
	from rheinwerk_mes.execution_gating import side_effects

	assert side_effects.release_order_reservations(order.name) == 0, "release is idempotent"


def test_completed_order_keeps_its_reservations(site):
	"""URS-W1-009 · TC-W1-010 — only Declined/Abandoned release; other states do not."""
	order = submitted_order(site, FIRST_ORDER, state=exec_state.IN_PROGRESS)
	set_fields(site, order, planned_end_date=PLANNED_END, produced_qty=500)
	reservations.reserve_for_order(order.name)

	exec_state.transition(order, exec_state.COMPLETED)

	assert site.get_all("Stock Reservation Entry", filters={"voucher_no": order.name}) != []


def test_gate_registration_order_is_committed(site):
	"""URS-W1-005…008 — the four gates are registered through the documented hook, in order."""
	registered = frappe.get_hooks(exec_state.GATE_HOOK)
	expected = [
		"rheinwerk_mes.execution_gating.gates.acceptance_gate",
		"rheinwerk_mes.execution_gating.gates.recipe_accepted_gate",
		"rheinwerk_mes.execution_gating.gates.completion_gate",
		"rheinwerk_mes.execution_gating.gates.material_availability_gate",
	]
	assert [path for path in registered if path in expected] == expected


def test_gate_refusals_are_logged(site):
	"""URS-W1-033 — a refused gate writes an immutable audit row (detail for TC-W1-036)."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(site, order, production_line=None)

	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)

	entries = audit.entries_for("Work Order", SECOND_ORDER)
	assert [entry for entry in entries if entry["gate"] == "acceptance_gate"]


def test_force_state_helper_is_arrangement_only(site):
	"""Guard: the helper writes `exec_state` directly and never runs the machine."""
	order = submitted_order(site, FIRST_ORDER)
	force_state(site, order, exec_state.COMPLETED)
	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.COMPLETED
