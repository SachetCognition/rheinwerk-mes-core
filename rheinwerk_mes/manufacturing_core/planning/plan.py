"""Production Plan creation from sales input and the planning-queue model (URS-W3-001).

The anchor `Production Plan` is adopted unchanged for the plan record (programme rule 1):
`create_production_plan` maps a list of sales-demand rows onto the anchor `po_items`, pins
the raw-material warehouse the netting scopes to and the target production line the orders
inherit, resolves each line's recipe through the Accepted-only gate (`recipe.plannable_bom`,
URS-W3-002) and submits the plan so it becomes a firm entry in the planning queue.

`planning_queue` is the read model the Desk page and the acceptance tests share: the
submitted plans and the Work Orders generated from them, each carrying the one status pill
used everywhere (`manufacturing_core.shopfloor.terminal.state_pill`) and German-first mass
(kg) and date (DD.MM.YYYY) rendering.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import frappe
from frappe import _
from frappe.utils import formatdate, nowdate

from rheinwerk_mes.execution_gating.gates import kg
from rheinwerk_mes.manufacturing_core.exec_state import INITIAL_STATE
from rheinwerk_mes.manufacturing_core.planning.recipe import plannable_bom
from rheinwerk_mes.manufacturing_core.shopfloor.terminal import state_pill

PRODUCTION_LINE_FIELD = "rw_production_line"
PLANNER_FIELD = "rw_planner"
RAW_WAREHOUSE_FIELD = "rw_raw_warehouse"


def create_production_plan(
	demand: Iterable[Mapping[str, object]],
	*,
	company: str,
	raw_warehouse: str,
	production_line: str | None = None,
	planner: str | None = None,
	submit: bool = True,
) -> object:
	"""Create (and by default submit) a Production Plan from sales-demand rows.

	Each `demand` row needs `item_code`, `qty` and the finished-goods `warehouse`; an
	optional `bom` picks a recipe version and `planned_start_date` the schedule anchor. The
	recipe of every row is validated as Accepted before it enters the plan, so a Draft recipe
	is refused here at the plan's front door as well as during explosion (URS-W3-002).
	"""
	plan = frappe.new_doc("Production Plan")
	plan.company = company
	plan.posting_date = nowdate()
	plan.get_items_from = "Sales Order"
	if plan.meta.has_field(RAW_WAREHOUSE_FIELD):
		plan.set(RAW_WAREHOUSE_FIELD, raw_warehouse)
	if production_line and plan.meta.has_field(PRODUCTION_LINE_FIELD):
		plan.set(PRODUCTION_LINE_FIELD, production_line)
	if planner and plan.meta.has_field(PLANNER_FIELD):
		plan.set(PLANNER_FIELD, planner)

	for row in demand:
		item_code = row["item_code"]
		bom_no = plannable_bom(item_code, row.get("bom"))
		plan.append(
			"po_items",
			{
				"item_code": item_code,
				"bom_no": bom_no,
				"planned_qty": row["qty"],
				"warehouse": row["warehouse"],
				"stock_uom": frappe.db.get_value("Item", item_code, "stock_uom"),
				"planned_start_date": row.get("planned_start_date") or nowdate(),
			},
		)

	plan.flags.ignore_permissions = True
	plan.insert(ignore_permissions=True)
	if submit:
		plan.submit()
	return plan


def planning_queue() -> dict[str, list[dict[str, object]]]:
	"""Read model of the planning queue: submitted plans and their generated orders."""
	plans = frappe.get_all(
		"Production Plan",
		filters={"docstatus": 1},
		fields=["name", "company", "posting_date", PRODUCTION_LINE_FIELD],
		order_by="creation desc",
	)
	plan_rows = [_plan_row(plan) for plan in plans]
	order_rows = [_order_row(order) for order in _generated_orders()]
	return {"plans": plan_rows, "orders": order_rows}


def _plan_row(plan: Mapping[str, object]) -> dict[str, object]:
	return {
		"name": plan["name"],
		"company": plan["company"],
		"production_line": plan.get(PRODUCTION_LINE_FIELD),
		"posting_date": plan["posting_date"],
		"posting_date_display": _de_date(plan["posting_date"]),
		"order_count": frappe.db.count("Work Order", {"production_plan": plan["name"]}),
	}


def _generated_orders() -> list[dict[str, object]]:
	return frappe.get_all(
		"Work Order",
		filters={"production_plan": ["is", "set"]},
		fields=[
			"name",
			"production_item",
			"item_name",
			"qty",
			"exec_state",
			"production_line",
			"production_plan",
			"planned_start_date",
		],
		order_by="creation desc",
	)


def _order_row(order: Mapping[str, object]) -> dict[str, object]:
	state = order.get("exec_state") or INITIAL_STATE
	return {
		"name": order["name"],
		"production_item": order["production_item"],
		"item_name": order.get("item_name"),
		"qty": order["qty"],
		"qty_display": kg(order["qty"]),
		"production_line": order.get("production_line"),
		"production_plan": order.get("production_plan"),
		"planned_start_display": _de_date(order.get("planned_start_date")),
		"exec_state": state,
		"pill": {**state_pill(state), "label": _(state)},
	}


def _de_date(value: object) -> str:
	if not value:
		return ""
	return formatdate(value, "dd.MM.yyyy")
