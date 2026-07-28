"""Recursive gross BOM explosion for planning (URS-W3-002).

Re-expresses the substrate's multi-level explosion
(`erpnext/manufacturing/doctype/production_plan/services/material_request.py:141`,
`get_items_for_material_requests` → `bom_explosion.get_subitems`) as a *gross* requirement
walk: every level is gated through `recipe.assert_plannable`, so a Draft sub-assembly recipe
is refused exactly like a Draft top-level recipe (URS-W3-002 AC-2). Netting against stock is
deliberately *not* done here — it is the separate `netting` concern (URS-W3-003), which uses
the W2 availability truth rather than the anchor's Bin projection.

The walk stops at leaf raw materials; a row that carries a sub-assembly recipe (`bom_no`)
is recursed into and never emitted as a requirement of its own.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal

import frappe

from rheinwerk_mes.manufacturing_core.planning.recipe import assert_plannable


@dataclass(frozen=True)
class ExplodedRequirement:
	"""One leaf raw-material requirement produced by the explosion."""

	item_code: str
	qty: Decimal
	stock_uom: str


def _decimal(value: object) -> Decimal:
	return Decimal(str(value or 0))


def gross_requirements(bom_no: str, planned_qty: object) -> list[ExplodedRequirement]:
	"""Gross leaf requirements to make `planned_qty` of the recipe `bom_no`.

	Recurses through sub-assembly recipes; every recipe touched must be Accepted
	(`assert_plannable`), so a Draft recipe anywhere in the tree refuses the whole plan.
	Quantities accumulate per raw material and are returned in first-seen order.
	"""
	accumulator: OrderedDict[str, Decimal] = OrderedDict()
	uoms: dict[str, str] = {}
	_explode(bom_no, _decimal(planned_qty), accumulator, uoms)
	return [
		ExplodedRequirement(item_code=item, qty=qty, stock_uom=uoms.get(item, ""))
		for item, qty in accumulator.items()
	]


def _explode(
	bom_no: str,
	planned_qty: Decimal,
	accumulator: OrderedDict[str, Decimal],
	uoms: dict[str, str],
) -> None:
	assert_plannable(bom_no)
	bom = frappe.get_doc("BOM", bom_no)
	batch_size = _decimal(bom.quantity) or Decimal("1")
	factor = planned_qty / batch_size

	for row in bom.items:
		required = factor * _decimal(row.stock_qty)
		if row.bom_no:
			_explode(row.bom_no, required, accumulator, uoms)
			continue
		accumulator[row.item_code] = accumulator.get(row.item_code, Decimal("0")) + required
		uoms.setdefault(row.item_code, row.stock_uom or "")
