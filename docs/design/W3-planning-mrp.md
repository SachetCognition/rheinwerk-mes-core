# W3-1 — Produktionsplanung & MRP-Reise

Design note for the planning module (`rheinwerk_mes/manufacturing_core/planning/**`) and its
installer (`rheinwerk_mes/setup/w3_planning.py`). It implements the master-scheduling front of
the programme: turn a sales demand into a firm Production Plan, explode its recipes, net the
requirements against the real ledger truth and generate execution-ready Work Orders.

Implements URS-W3-001 … URS-W3-004 of `docs/urs/URS-W3-planning-boundary.md`; test coverage
TC-W3-001 … TC-W3-005 (`tests/acceptance/test_w3_planning_journey.py`). The scheduling layer
(URS-W3-005…, `manufacturing_core/scheduling/**`) is a sibling child and out of scope here.

## 1. Substrate adoption — no anchor fork

The journey rides unmodified ERPNext anchors; the app only adds Custom Fields to the anchor
`Production Plan`, installed idempotently by `setup/w3_planning.py` (`after_install` +
`patches.txt`, mirroring W1/W2):

| Field on `Production Plan` | Type | Purpose |
|---|---|---|
| `rw_production_line` | Link `Production Line` | target Fertigungslinie the generated Work Orders inherit (CDM-08) |
| `rw_planner` | Link `User` | responsible planner (persona `p.krueger@…`) for the queue view |
| `rw_raw_warehouse` | Link `Warehouse` | leaf raw-material warehouse the MRP nets availability against |

`rw_raw_warehouse` exists because the anchor's own `raw_material_group_warehouse` must be a
**group** warehouse, whereas the programme nets against the concrete leaf `RM Lager Nord`.
No anchor DocType, controller or field is edited.

## 2. Module surface

| Module | Public API | Requirement |
|---|---|---|
| `recipe` | `plannable_bom(item, bom=None)`, `assert_plannable(bom)` | URS-W3-002 (Accepted-only gate) |
| `explosion` | `gross_requirements(bom, qty) -> [ExplodedRequirement]` | URS-W3-002 (recursive explosion) |
| `netting` | `net_requirements(plan) -> [NetRow]`, `generate_material_requests(plan)` | URS-W3-003 |
| `orders` | `generate_orders(plan) -> [work_order]` | URS-W3-004 |
| `plan` | `create_production_plan(demand, …)`, `planning_queue()` | URS-W3-001 |
| `view` | `get_planning_queue()` (whitelisted) | queue Desk page |

### 2.1 Accepted-only recipe gate (URS-W3-002)

`assert_plannable` reads `recipe_isa88.governance.gov_state` (W1-4) and only lets an
`Accepted` recipe through. A Draft (or otherwise non-Accepted) reference is refused as a
**hard gate** — a raised modal naming **rule** (only Accepted recipes are plannable),
**record** (the BOM id and its governance state) and **resolution** (release it or pick an
Accepted version) via the shared `execution_gating.gates.hard_gate_message` — and the refusal
is written to the immutable `Execution Gate Log` through `execution_gating.audit.log_refusal`
(gate id `planning_recipe_accepted`). This is the master-scheduling twin of the W1
`recipe_accepted_gate` on order acceptance. Neither the governance API nor the audit log is
re-implemented.

_Absorb reference:_ Qcadoo `TechnologyState.java:33-66` — a master plan may reference only
*accepted* technologies (re-expressed, not ported).

### 2.2 Recursive gross explosion (URS-W3-002)

`gross_requirements` walks the BOM tree — `factor = planned_qty / bom.quantity`, each leaf
row contributing `factor · stock_qty`, sub-assembly rows recursed into and never emitted —
and gates **every** level through `assert_plannable`, so a Draft sub-assembly refuses the
whole plan. It re-expresses the substrate's multi-level walk
(`erpnext/.../production_plan/services/material_request.py:141`, `get_items_for_material_requests`)
as a pure *gross* requirement list; netting is a separate concern (§2.3).

### 2.3 MRP netting on W2 truth (URS-W3-003)

The anchor nets against the `Bin` projected quantity, which counts Blocked/Quarantined lots
as on hand. The programme instead nets against the **W2 availability predicate**
`warehouse.availability.available_qty`, which is on-hand − live reservations −
`genealogy.blocking.excluded_qty` (Blocked/Quarantined). Net shortage = gross − available;
a single Purchase `Material Request` (Draft) is created **only** for positive shortages, each
row carrying the anchor `production_plan` back-link. Requirements are aggregated across plan
lines first, so a shared raw material is netted once. The exclusion predicate is reused,
never re-implemented (W2 boundary).

### 2.4 Order generation into Pending (URS-W3-004)

`generate_orders` creates one anchor `Work Order` per plan line, re-checks the recipe gate,
links `production_plan`/`production_plan_item`, carries `rw_production_line` onto the order's
`production_line` and enters the W1 `exec_state` machine in **Pending** with a `state_history`
genesis row (creator + timestamp). The `exec_state` machine, its history schema and the audit
trail are reused (W1 boundary). _Absorb reference:_ Qcadoo `WorkOrderCreationService`.

## 3. Planning queue (German-first UI)

`plan.planning_queue()` is the read model shared by the Desk page
(`manufacturing_core/page/planning_queue`) and the acceptance tests: firm plans plus the Work
Orders generated from them. Every order carries the one status pill used everywhere
(`shopfloor.terminal.state_pill` — icon + label + colour), mass in **kg**
(`execution_gating.gates.kg`) and dates as **DD.MM.YYYY**; the exact state label is `Pending`
(no synonym). All strings go through `frappe._()`. The page lives under the module's `page/`
directory (Frappe discovers Desk pages at `<module>/page/<name>`) while its logic stays in the
`planning` package.

## 4. Fixture reconciliation (decision)

URS-W3-002 AC-1 requires 500 kg RW-CHM-0003 → exactly **400 kg RW-CHM-0001 + 20 kg
RW-CHM-0002** (a 20 kg + 1 kg per 25 kg recipe). The **seeded canonical** `BOM-RW-CHM-0003-001`
carries a different ratio (80 kg + 20 kg per 100 kg) that the merged W0/W1 suites depend on —
the W1 material-availability shortfall arithmetic is pinned to 100 kg additive, and the W0
versioned-naming case asserts that copying the canonical BOM yields `…-002`. Re-shaping the
seeded BOM would break those committed tests (which this child may not edit), and seeding a
*second* persistent RW-CHM-0003 BOM would break the versioned-naming assertion.

**Decision:** the AC-1 arithmetic is proven against an **Accepted compound recipe at the
URS-W3-002 ratio, built as a versioned successor inside the (rolled-back) site-backed test**
(`test_w3_planning_support.accepted_compound_recipe`). The literal `BOM-RW-CHM-0003-001` in the
AC is read as "the Accepted compound recipe for RW-CHM-0003"; the canonical BOM keeps its
W0/W1 ratio. The explosion assertion still checks the exact 400 kg + 20 kg — the recipe is a
real fixture, not a fudged expectation. This is the reading most consistent with the dossier
(programme rule 7) and does not touch any authoritative `docs/urs/**` or `docs/test/**`.

## 5. Traceability

| URS | Requirement | Test case |
|---|---|---|
| URS-W3-001 | Production Plan creation from sales input | TC-W3-001 |
| URS-W3-002 | BOM explosion incl. sub-assemblies; Draft recipe refused | TC-W3-002, TC-W3-003 |
| URS-W3-003 | MRP netting vs ledger/reservations; Blocked stock excluded | TC-W3-004 |
| URS-W3-004 | Order generation into `exec_state` Pending with history | TC-W3-005 |
