"""Work Order generation from a Production Plan (URS-W3-004).

Adopts the anchor `Work Order` and the anchor `production_plan` back-link
(`work_order.json`) — never a fork. The anchor's own
`WorkOrderCreationService.create_work_order` is the behavioural reference; it is
re-expressed here so the two programme obligations the anchor does not carry are met:

* the generated order enters the `exec_state` machine in **Pending** (the substrate's
  `before_insert` hook sets it) and its `state_history` gets the genesis row recording
  creator and timestamp (URS-W3-004 AC-1);
* the target production line from the plan is carried onto the order
  (`production_line`, CDM-08), so the shop-floor queue can group by line.

The `exec_state` machine, its `state_history` schema and the audit trail are reused, never
re-implemented (W1 boundary): the genesis row uses the very `Order State History` child the
machine appends, and `Work Order.on_update` logs the creation to the Execution Gate Log.
"""

from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import flt, now_datetime

from rheinwerk_mes.manufacturing_core.exec_state import INITIAL_STATE
from rheinwerk_mes.manufacturing_core.planning.recipe import assert_plannable


def generate_orders(plan: object) -> list[str]:
	"""Generate one anchor Work Order per plan line into Pending (URS-W3-004).

	Each line's recipe is re-checked through `assert_plannable` (defence in depth — the plan
	cannot have been built without it, but generation must never emit an order against a
	Draft recipe). Orders already generated for a line are not duplicated.
	"""
	from erpnext.manufacturing.doctype.work_order.work_order import get_default_warehouse

	defaults = get_default_warehouse(plan.company)
	created: list[str] = []
	for line in plan.po_items:
		if _already_ordered(plan, line):
			continue
		qty = Decimal(str(flt(line.planned_qty) - flt(line.ordered_qty)))
		if qty <= 0:
			continue
		assert_plannable(line.bom_no)
		created.append(_create_order(plan, line, qty, defaults))
	return created


def _already_ordered(plan: object, line: object) -> bool:
	"""A non-cancelled Work Order already links this plan line — generation stays idempotent.

	Generated orders are inserted as drafts, so the anchor never bumps the line's
	`ordered_qty`; the `planned_qty - ordered_qty` guard alone would regenerate every order on
	a re-run. The `production_plan` / `production_plan_item` back-link is the durable marker.
	"""
	return bool(
		frappe.db.exists(
			"Work Order",
			{
				"production_plan": plan.name,
				"production_plan_item": line.name,
				"docstatus": ["<", 2],
			},
		)
	)


def _create_order(plan: object, line: object, qty: Decimal, defaults: dict) -> str:
	wo = frappe.new_doc("Work Order")
	wo.update(
		{
			"production_item": line.item_code,
			"bom_no": line.bom_no,
			"qty": float(qty),
			"company": plan.company,
			"stock_uom": line.stock_uom or frappe.db.get_value("Item", line.item_code, "stock_uom"),
			"fg_warehouse": line.warehouse or defaults.get("fg_warehouse"),
			"wip_warehouse": defaults.get("wip_warehouse"),
			"scrap_warehouse": defaults.get("scrap_warehouse"),
			"production_plan": plan.name,
			"production_plan_item": line.name,
			"planned_start_date": line.planned_start_date,
			"use_multi_level_bom": 1,
		}
	)
	if plan.get("rw_production_line") and wo.meta.has_field("production_line"):
		wo.production_line = plan.get("rw_production_line")
	if not wo.source_warehouse:
		wo.source_warehouse = wo.wip_warehouse or wo.fg_warehouse

	wo.set_work_order_operations()
	wo.set_required_items(reset_source_warehouse=True)
	_append_genesis_history(wo)

	wo.flags.ignore_mandatory = True
	wo.flags.ignore_validate = True
	wo.insert(ignore_permissions=True)
	return wo.name


def _append_genesis_history(wo: object) -> None:
	"""Record the creation of the order in Pending (URS-W3-004 AC-1).

	Uses the same `Order State History` child the W1 state machine appends on a transition;
	the genesis row has no `from_state` because Pending is the entry state.
	"""
	if not wo.meta.has_field("state_history"):
		return
	wo.exec_state = INITIAL_STATE
	wo.append(
		"state_history",
		{
			"from_state": None,
			"to_state": INITIAL_STATE,
			"changed_by": frappe.session.user,
			"changed_at": now_datetime(),
		},
	)
