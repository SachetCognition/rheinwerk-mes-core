"""W3-1 — Production Plan / MRP journey (manufacturing_core → planning).

Covers the five mapped test cases of `docs/test/TST-W3-planning-boundary.md`:

* TC-W3-001 (URS-W3-001) — create a Production Plan from sales input.
* TC-W3-002 (URS-W3-002) — BOM explosion arithmetic through an Accepted recipe.
* TC-W3-003 (URS-W3-002 AC-2) — a Draft recipe is refused, modally and audited.
* TC-W3-004 (URS-W3-003) — MRP netting ignores Blocked stock and requests only shortages.
* TC-W3-005 (URS-W3-004) — orders generate into `exec_state` Pending with history + pill.

Site-backed: the suite skips (never fails) when the Frappe substrate is absent.
"""

from __future__ import annotations

import re

import pytest

frappe = pytest.importorskip("frappe")
planning = pytest.importorskip("rheinwerk_mes.manufacturing_core.planning")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

from test_w3_planning_support import (  # noqa: E402  (import after the substrate check)
	FG_WAREHOUSE,
	ITEM_A,
	ITEM_B,
	ITEM_FG,
	LINE,
	PLANNER,
	RM_WAREHOUSE,
	accepted_compound_recipe,
	block_all_stock,
	draft_compound_recipe,
	receive_released_stock,
)

COMPANY = "Rheinwerk Chemie GmbH"
DE_DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")

PLAN_DEMAND = {"item_code": ITEM_FG, "qty": 500, "warehouse": FG_WAREHOUSE}


def _plan(site, bom_no: str):
	return planning.create_production_plan(
		[{**PLAN_DEMAND, "bom": bom_no}],
		company=COMPANY,
		raw_warehouse=RM_WAREHOUSE,
		production_line=LINE,
		planner=PLANNER,
	)


# --------------------------------------------------------------------------------------
# TC-W3-001 — Create Production Plan from sales input (URS-W3-001)
# --------------------------------------------------------------------------------------


def test_tc_w3_001_create_production_plan_from_sales_input(site):
	"""URS-W3-001 · TC-W3-001 — a 500 kg RW-CHM-0003 sales input becomes a submitted plan.

	Step 1: one plan row RW-CHM-0003 / 500 kg / FG Lager Süd. Step 2: submitted and
	non-editable, visible in the planning queue. Step 3: the queue renders the plan
	German-first (DD.MM.YYYY date).
	"""
	bom_no = accepted_compound_recipe(site)
	plan = _plan(site, bom_no)

	assert len(plan.po_items) == 1
	row = plan.po_items[0]
	assert (row.item_code, float(row.planned_qty), row.warehouse) == (ITEM_FG, 500.0, FG_WAREHOUSE)
	assert plan.docstatus == 1, "submitted plan is non-editable"

	queue = planning.planning_queue()
	plan_row = next(p for p in queue["plans"] if p["name"] == plan.name)
	assert plan_row["production_line"] == LINE
	assert DE_DATE.match(plan_row["posting_date_display"]), "date rendered DD.MM.YYYY"


# --------------------------------------------------------------------------------------
# TC-W3-002 — BOM explosion quantities (URS-W3-002)
# --------------------------------------------------------------------------------------


def test_tc_w3_002_bom_explosion_quantities(site):
	"""URS-W3-002 · TC-W3-002 — exploding 500 kg RW-CHM-0003 yields exactly 400 kg + 20 kg.

	The Accepted compound recipe consumes 20 kg RW-CHM-0001 + 1 kg RW-CHM-0002 per 25 kg
	output, so a 500 kg plan needs exactly 400 kg base resin and 20 kg additive.
	"""
	bom_no = accepted_compound_recipe(site)
	requirements = {r.item_code: r.qty for r in planning.gross_requirements(bom_no, 500)}

	assert set(requirements) == {ITEM_A, ITEM_B}
	assert float(requirements[ITEM_A]) == pytest.approx(400.0, abs=1e-3)
	assert float(requirements[ITEM_B]) == pytest.approx(20.0, abs=1e-3)


# --------------------------------------------------------------------------------------
# TC-W3-003 — Non-Accepted recipe refused with gate-refusal presentation (URS-W3-002 AC-2)
# --------------------------------------------------------------------------------------


def test_tc_w3_003_draft_recipe_refused_and_audited(site):
	"""URS-W3-002 AC-2 · TC-W3-003 — planning a Draft recipe is a modal, audited refusal.

	Step 1: the refusal is a raised hard gate (never a toast) naming the rule (only Accepted
	recipes are plannable), the record (the Draft BOM id) and the resolution. Step 2: the
	refusal is written to the immutable audit log.
	"""
	draft_bom = draft_compound_recipe(site)

	with pytest.raises(frappe.ValidationError) as excinfo:
		planning.gross_requirements(draft_bom, 500)

	message = str(excinfo.value)
	assert "Regel:" in message and "Behebung:" in message, "hard gate names rule + resolution"
	assert draft_bom in message, "hard gate names the offending record"
	assert "Accepted" in message, "the rule cites the Accepted requirement"

	entries = audit.entries_for("BOM", draft_bom)
	assert [e["outcome"] for e in entries] == [audit.REFUSED]
	assert entries[0]["gate"] == "planning_recipe_accepted"


# --------------------------------------------------------------------------------------
# TC-W3-004 — MRP netting vs ledger, reservations and Blocked stock (URS-W3-003)
# --------------------------------------------------------------------------------------


def test_tc_w3_004_netting_ignores_blocked_stock(site):
	"""URS-W3-003 · TC-W3-004 — netting counts only available stock (W2 predicate).

	Base resin is on hand and Released (≥ 400 kg) so no Material Request is raised for it;
	the additive's only stock is Blocked, so the W2 exclusion predicate treats it as
	unavailable and a Material Request for the 20 kg net shortage is generated.
	"""
	bom_no = accepted_compound_recipe(site)
	receive_released_stock(site, ITEM_A, 600)
	assert block_all_stock(site, ITEM_B) >= 1, "the additive's stock must be Blocked"

	plan = _plan(site, bom_no)
	net = {r.item_code: r for r in planning.net_requirements(plan)}
	assert not net[ITEM_A].is_short, "sufficient Released base resin raises no request"
	assert float(net[ITEM_B].shortage) == pytest.approx(20.0, abs=1e-3), "Blocked stock not counted"

	requests = planning.generate_material_requests(plan)
	assert len(requests) == 1
	lines = frappe.get_doc("Material Request", requests[0]).items
	assert [(li.item_code, float(li.qty)) for li in lines] == [(ITEM_B, 20.0)]


# --------------------------------------------------------------------------------------
# TC-W3-005 — Order generation in exec_state Pending (URS-W3-004)
# --------------------------------------------------------------------------------------


def test_tc_w3_005_order_generation_pending_with_pill(site):
	"""URS-W3-004 · TC-W3-005 — generation yields a Pending order with history and a pill.

	Step 1: the generated order is 500 kg RW-CHM-0003 on LINE-1 in `exec_state` Pending, and
	its `state_history` genesis row records creator and timestamp. Step 2: the queue shows
	the state as a status pill (icon + label + colour) with the exact label "Pending".
	"""
	bom_no = accepted_compound_recipe(site)
	plan = _plan(site, bom_no)

	orders = planning.generate_orders(plan)
	assert len(orders) == 1
	order = frappe.get_doc("Work Order", orders[0])
	assert order.production_item == ITEM_FG
	assert float(order.qty) == 500.0
	assert order.production_line == LINE
	assert order.production_plan == plan.name
	assert order.exec_state == exec_state.PENDING

	history = exec_state.state_history(order.name)
	assert history[-1]["to_state"] == exec_state.PENDING
	assert history[-1]["changed_by"] and history[-1]["changed_at"], "creator + timestamp recorded"

	queue = planning.planning_queue()
	order_row = next(o for o in queue["orders"] if o["name"] == order.name)
	pill = order_row["pill"]
	assert pill["state"] == "Pending", "exact state, no synonym"
	assert pill["label"] == "Pending"
	assert pill["icon"], "the pill carries an icon (never colour-only)"
	assert order_row["qty_display"].endswith("kg"), "mass rendered in kg"
