"""MRP netting for a Production Plan (URS-W3-003).

Re-expresses the anchor Material Request planning
(`erpnext/manufacturing/doctype/production_plan/services/material_request.py:141`,
`get_items_for_material_requests` → `get_material_request_items`) but replaces its stock
truth: the anchor nets against the Bin `projected_qty`, which counts Blocked and
Quarantined lots as on hand. The programme's netting instead calls the **W2 availability
predicate** `warehouse.availability.available_qty`, which is on-hand minus live reservations
minus the genealogy exclusion (`genealogy.blocking.excluded_qty`) — so Blocked/Quarantined
stock is never available and never suppresses a Material Request (URS-W3-003 AC-2). The
exclusion predicate itself is reused, never re-implemented (programme rule 3 / W2 boundary).

Net shortage = gross requirement − available; a Material Request is generated **only** for a
positive shortage (URS-W3-003 AC-1).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_days, nowdate

from rheinwerk_mes.manufacturing_core.planning.explosion import ExplodedRequirement, gross_requirements
from rheinwerk_mes.warehouse.availability import available_qty

MATERIAL_REQUEST_TYPE = "Purchase"


@dataclass(frozen=True)
class NetRow:
	"""Netting verdict for one raw material against one warehouse."""

	item_code: str
	warehouse: str
	required: Decimal
	available: Decimal
	shortage: Decimal
	stock_uom: str

	@property
	def is_short(self) -> bool:
		return self.shortage > 0


def net_requirements(plan: object, warehouse: str | None = None) -> list[NetRow]:
	"""Net every plan requirement against W2 availability in the raw-material warehouse.

	Gross requirements are aggregated across all plan lines first, so a raw material shared
	by several finished goods is netted against its availability once (never double-counted).
	"""
	source_warehouse = warehouse or _raw_warehouse(plan)
	rows: list[NetRow] = []
	for req in _aggregate_requirements(plan):
		available = Decimal(str(available_qty(req.item_code, source_warehouse)))
		shortage = req.qty - available
		rows.append(
			NetRow(
				item_code=req.item_code,
				warehouse=source_warehouse,
				required=req.qty,
				available=available,
				shortage=shortage if shortage > 0 else Decimal("0"),
				stock_uom=req.stock_uom,
			)
		)
	return rows


def _aggregate_requirements(plan: object) -> list[ExplodedRequirement]:
	totals: OrderedDict[str, Decimal] = OrderedDict()
	uoms: dict[str, str] = {}
	for line in plan.po_items:
		for req in gross_requirements(line.bom_no, line.planned_qty):
			totals[req.item_code] = totals.get(req.item_code, Decimal("0")) + req.qty
			uoms.setdefault(req.item_code, req.stock_uom)
	return [
		ExplodedRequirement(item_code=item, qty=qty, stock_uom=uoms.get(item, ""))
		for item, qty in totals.items()
	]


def generate_material_requests(plan: object, warehouse: str | None = None) -> list[str]:
	"""Create a Material Request for the net shortages of `plan` (URS-W3-003 AC-1).

	Nothing is requested when stock covers every requirement; otherwise one Purchase
	Material Request is created (Draft), each row carrying the `production_plan` back-link
	the anchor keeps (`material_request.py:118`). Returns the created request names.
	"""
	shortages = [row for row in net_requirements(plan, warehouse) if row.is_short]
	if not shortages:
		return []

	request = frappe.new_doc("Material Request")
	request.material_request_type = MATERIAL_REQUEST_TYPE
	request.company = plan.company
	request.transaction_date = nowdate()
	request.schedule_date = add_days(nowdate(), 1)
	for row in shortages:
		request.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": float(row.shortage),
				"warehouse": row.warehouse,
				"schedule_date": add_days(nowdate(), 1),
				"production_plan": plan.name,
			},
		)
	request.flags.ignore_permissions = True
	request.insert(ignore_permissions=True)
	return [request.name]


def _raw_warehouse(plan: object) -> str:
	warehouse = plan.get("rw_raw_warehouse")
	if not warehouse:
		frappe.throw(_("Für die Bedarfsrechnung ist kein Rohstofflager am Produktionsplan hinterlegt."))
	return warehouse
