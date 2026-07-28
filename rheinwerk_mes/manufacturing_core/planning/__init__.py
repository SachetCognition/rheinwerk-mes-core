"""Wave W3-1 — Production Plan / MRP journey (manufacturing_core → planning).

The package re-expresses the Qcadoo *master production scheduling* behaviour on top of
the unmodified ERPNext substrate: the anchor `Production Plan` is adopted for the plan
record, the anchor `Work Order` for the generated orders and the anchor Material Request
netting semantics (`erpnext/manufacturing/doctype/production_plan/services/material_request.py:141`,
`get_items_for_material_requests`) for the shortage arithmetic — never forked, never ported.

Everything the anchors do not enforce and the programme requires lives here:

* `recipe` — only `gov_state = Accepted` recipes are plannable; a Draft recipe reference is
  refused as a hard gate naming rule/record/resolution and audited (URS-W3-002).
* `explosion` — recursive gross BOM explosion incl. sub-assemblies, every level gated
  through `recipe.assert_plannable` (URS-W3-002).
* `netting` — net requirements against the anchor ledger truth via the W2 availability
  predicate (`warehouse.availability.available_qty`, which already subtracts live
  reservations and Blocked/Quarantined stock); Material Requests only for net shortages
  (URS-W3-003).
* `orders` — anchor Work Orders generated into `exec_state` Pending with a `state_history`
  genesis row, linked back to the plan (URS-W3-004).
* `view` — the German-first planning queue model (status pill, kg, DD.MM.YYYY).
"""

from __future__ import annotations

from rheinwerk_mes.manufacturing_core.planning.explosion import gross_requirements
from rheinwerk_mes.manufacturing_core.planning.netting import (
	generate_material_requests,
	net_requirements,
)
from rheinwerk_mes.manufacturing_core.planning.orders import generate_orders
from rheinwerk_mes.manufacturing_core.planning.plan import (
	create_production_plan,
	planning_queue,
)
from rheinwerk_mes.manufacturing_core.planning.recipe import assert_plannable, plannable_bom

__all__ = [
	"assert_plannable",
	"create_production_plan",
	"generate_material_requests",
	"generate_orders",
	"gross_requirements",
	"net_requirements",
	"plannable_bom",
	"planning_queue",
]
