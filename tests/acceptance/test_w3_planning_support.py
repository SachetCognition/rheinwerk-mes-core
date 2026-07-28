"""Shared fixtures/helpers for the W3-1 planning acceptance suite.

The programme fixtures (`Rheinwerk Chemie GmbH`, RW-CHM-0001/2/3, LINE-1, the RM/FG
warehouses, planner `p.krueger@…`) are the single dataset. Two things the merged W0/W1/W2
suites pin cannot be re-shaped in the seeder, so they are arranged here per test instead
(the `site` fixture rolls every write back):

* **The Accepted compound recipe at the URS-W3-002 ratio** (20 kg RW-CHM-0001 + 1 kg
  RW-CHM-0002 per 25 kg → exactly 400 kg + 20 kg for a 500 kg plan). The canonical
  `BOM-RW-CHM-0003-001` keeps its W0/W1 ratio (80/100 + 20/100), which the merged W1
  material-availability suite depends on, and seeding a *second* persistent RW-CHM-0003 BOM
  would rename the copy the W0 versioned-naming case asserts as `…-002`.
  `accepted_compound_recipe` therefore builds the AC-ratio recipe as a versioned successor
  inside the test — see `docs/design/W3-planning-mrp.md` § "Fixture reconciliation".
* **The Blocked-stock netting precondition**, arranged with the W2 `qa_state` API.
"""

from __future__ import annotations

import pytest

frappe = pytest.importorskip("frappe")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")

COMPANY = "Rheinwerk Chemie GmbH"
CANONICAL_BOM = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"

ITEM_FG = "RW-CHM-0003"
ITEM_A = "RW-CHM-0001"
ITEM_B = "RW-CHM-0002"

RM_WAREHOUSE = "RM Lager Nord - RWC"
FG_WAREHOUSE = "FG Lager Süd - RWC"
LINE = "LINE-1"
PLANNER = "p.krueger@rheinwerk-chemie.example"

#: URS-W3-002 AC-1 recipe ratio: per 25 kg compound, 20 kg base resin + 1 kg additive.
AC_BATCH_SIZE = 25
AC_RESIN_QTY = 20
AC_ADDITIVE_QTY = 1


def _compound_recipe(site) -> object:
	"""A submitted RW-CHM-0003 BOM at the URS-W3-002 ratio (rolled back with the test)."""
	bom = site.copy_doc(site.get_doc("BOM", CANONICAL_BOM))
	bom.quantity = AC_BATCH_SIZE
	bom.items = []
	bom.append("items", {"item_code": ITEM_A, "qty": AC_RESIN_QTY, "uom": "Kg", "stock_uom": "Kg"})
	bom.append("items", {"item_code": ITEM_B, "qty": AC_ADDITIVE_QTY, "uom": "Kg", "stock_uom": "Kg"})
	bom.is_default = 0
	bom.is_active = 1
	bom.insert(ignore_permissions=True)
	bom.submit()
	return bom


def _govern(bom_no: str, accept: bool) -> None:
	name = frappe.db.get_value("Recipe Governance", {"bom": bom_no}, "name")
	if not name:
		name = (
			frappe.get_doc({"doctype": "Recipe Governance", "bom": bom_no, "routing": ROUTING})
			.insert(ignore_permissions=True)
			.name
		)
	if accept:
		governance.transition(name, governance.CHECKED)
		governance.transition(name, governance.ACCEPTED)


def accepted_compound_recipe(site) -> str:
	"""Create and Accept the AC-ratio compound recipe; returns its BOM name."""
	bom = _compound_recipe(site)
	_govern(bom.name, accept=True)
	return bom.name


def draft_compound_recipe(site) -> str:
	"""Create the AC-ratio compound recipe governed but left in Draft; returns its name."""
	bom = _compound_recipe(site)
	_govern(bom.name, accept=False)
	return bom.name


def receive_released_stock(site, item: str, qty: float, warehouse: str = RM_WAREHOUSE) -> None:
	"""Book a plain Material Receipt so `item` is on hand and Released in `warehouse`."""
	entry = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"items": [{"item_code": item, "qty": qty, "t_warehouse": warehouse, "basic_rate": 2.0}],
		}
	)
	entry.insert(ignore_permissions=True)
	entry.submit()


def block_all_stock(site, item: str) -> int:
	"""Set every batch of `item` to `qa_state` Blocked (W2 API); returns the count blocked."""
	blocked = 0
	for batch in frappe.get_all("Batch", filters={"item": item}, pluck="name"):
		if qa_state.current_state(batch) != qa_state.BLOCKED:
			qa_state.transition(batch, qa_state.BLOCKED, reason="W3-1 Netting-Test")
			blocked += 1
	return blocked
