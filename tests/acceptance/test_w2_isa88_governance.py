"""W2-6 — ISA-88 recipes execute under the W1-4 `gov_state` governance (URS-W2-022).

TC-W2-030: a scaled recipe is a new governed BOM version in Draft; a production order may
not be accepted against it until it is Accepted, and once an active order references it the
recipe's in-use lock blocks structural edits — all via the existing W1-4 machinery.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
scaling = pytest.importorskip("rheinwerk_mes.recipe_isa88.scaling")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")

BOM_NAME = "BOM-RW-CHM-0003-001"
COMPANY_ABBR = "RWC"


def _require_recipe(site) -> str:
	name = site.db.get_value("ISA88 Recipe", {"bom": BOM_NAME}, "name")
	if not name:
		pytest.skip("ISA-88 recipe fixture not seeded on this site")
	return name


def _order_for(site, bom: str) -> object:
	"""A submitted Work Order in `exec_state` Pending referencing `bom`, with the
	acceptance-gate fields populated (an order must be booked before it can be accepted)."""
	from rheinwerk_mes.setup.naming import WORK_ORDER_SERIES

	item = site.db.get_value("BOM", bom, "item")
	doc = site.get_doc(
		{
			"doctype": "Work Order",
			"naming_series": WORK_ORDER_SERIES,
			"company": "Rheinwerk Chemie GmbH",
			"production_item": item,
			"bom_no": bom,
			"qty": 250.0,
			"stock_uom": site.db.get_value("Item", item, "stock_uom"),
			"wip_warehouse": f"RM Lager Nord - {COMPANY_ABBR}",
			"fg_warehouse": f"FG Lager Süd - {COMPANY_ABBR}",
			"planned_start_date": "2026-05-02 06:00:00",
			"planned_end_date": "2026-05-04 14:00:00",
			"production_line": "LINE-1",
		}
	)
	doc.insert()
	doc.submit()
	site.db.set_value("Work Order", doc.name, "exec_state", exec_state.PENDING, update_modified=False)
	doc.reload()
	return doc


def test_tc_w2_030_draft_scaled_recipe_blocks_order_acceptance(site):
	"""TC-W2-030 step 1 (URS-W2-022 AC-1): an order referencing the scaled recipe while it is
	still Draft cannot be accepted — the gate names the recipe and its `gov_state`."""
	scaled = scaling.scale_recipe(_require_recipe(site), 250)
	assert governance.gov_state(scaled.bom) == governance.DRAFT

	order = _order_for(site, scaled.bom)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		exec_state.transition(order.name, exec_state.ACCEPTED)
	message = str(refusal.value)
	assert scaled.bom in message
	assert "Draft" in message


def test_tc_w2_030_accepted_scaled_recipe_lets_the_order_proceed(site):
	"""TC-W2-030 step 2 (URS-W2-022 AC-1): once the scaled recipe passes the validators and
	becomes Accepted, an order referencing it accepts."""
	scaled = scaling.scale_recipe(_require_recipe(site), 250)
	record = site.get_doc("Recipe Governance", governance.governance_name(scaled.bom))
	governance.transition(record, governance.CHECKED)
	governance.transition(record, governance.ACCEPTED)
	assert governance.gov_state(scaled.bom) == governance.ACCEPTED

	order = _order_for(site, scaled.bom)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.ACCEPTED


def test_tc_w2_030_in_use_lock_blocks_structural_edit(site):
	"""TC-W2-030 step 3 (URS-W2-022 AC-2): while an active order references the Accepted
	scaled recipe, the in-use lock refuses a structural change, naming the order."""
	scaled = scaling.scale_recipe(_require_recipe(site), 250)
	record = site.get_doc("Recipe Governance", governance.governance_name(scaled.bom))
	governance.transition(record, governance.CHECKED)
	governance.transition(record, governance.ACCEPTED)

	order = _order_for(site, scaled.bom)
	exec_state.transition(order.name, exec_state.ACCEPTED)

	assert governance.active_orders_for_recipe(scaled.bom) == [order.name]
	bom = site.get_doc("BOM", scaled.bom)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		bom.cancel()
	message = str(refusal.value)
	assert order.name in message
	assert "Verwendungssperre" in message or scaled.bom in message
