# URS W3 — Planning & Boundary

**Programme:** Rheinwerk Chemie GmbH MES consolidation — User Requirements Specification, Wave W3
**Sources:** `docs/waves/W3-planning-boundary.md` (W3-1…W3-7) · `CONSOLIDATION.md` · `docs/adr/ADR-002` · `docs/canonical-model/README.md` (CDM-02, CDM-03, CDM-08) · `docs/dossier/production-systems-dossier.md` §3.1/§3.2, §5.3, §6.2, §6.3, §7, §8.2 · `rheinwerk-mes-design-SKILL.md`
**Requirement count:** 23 (within the 15–25 sizing guide).

---

## 1. Purpose & scope

Wave W3 delivers the planning journey and the system boundary of the consolidated MES: the Production Plan/MRP journey on the anchor (sales input → explosion → material requests → production orders), a finite-capacity scheduling layer absorbing Qcadoo line-schedule and TJ/TPZ realization-time semantics over the anchor slot search, the group-ERP interface (orders in, confirmations out, GL postings out) with contract fixtures per ADR-002, boundary costing/GL account mapping, the net-new SCADA/OPC-UA adapter, hazmat/regulatory completion at the shipping boundary, and the survey + contract-freeze of existing external syncs.

**Out of scope for W3** (visible scope fences, pulled from other waves):

- Order state machine, execution gating, recipe governance, warehouse fidelity base — delivered in W1 (`docs/waves/W1-production-core.md`); W3 consumes them as dependencies.
- Genealogy, batch blocking, QI, CoA, ISA-88, hazmat master data (UN numbers, SDS references, storage classes on Item/Batch) — delivered in W2 (`docs/waves/W2-traceability-quality.md`); W3 only *completes* hazmat at the shipping/label boundary (W3-6).
- Per-plant cutover, data backfill, legacy read-only/archival, decommission evidence — W4 (`docs/waves/W4-cutover-decommission.md`).
- Finance, buying, selling capabilities themselves — permanently across the ERP boundary per ADR-002 (never in the MES).
- A constraint-based finite-capacity **optimiser** — white space in all three legacy systems (dossier §6.3); explicitly excluded from W3 (see URS-W3-009).

## 2. Personas in scope

Subset of the six programme personas relevant to W3 (role model evidenced in dossier ch. 3.1 §B.2 — Qcadoo planner/kanban role family; ch. 3.2 personas — ERPNext `Manufacturing Manager`/`Manufacturing User`, `Accounts Manager` at the boundary):

| Persona | Fixture name | W3 relevance |
|---|---|---|
| planner | P. Krüger | Owns the Production Plan/MRP journey, line schedules, capacity decisions (dossier ch. 3.1 §B.2 "Production planner / supervisor": `ROLE_DASHBOARD_KANBAN*`) |
| shop-floor operator | O. Weber | Consumes SCADA-originated tracking events; confirms operations feeding boundary confirmations (dossier ch. 3.1 §B.2) |
| technologist | T. Schmid | Owns hazmat shipping/label data completion (white space, dossier §6.3) |
| warehouse clerk | W. Braun | Prints/validates hazmat shipping labels at dispatch (dossier ch. 3.1 §B.2 "Warehouse operator") |
| business viewer | B. Vogel | Reads planning KPIs and boundary-interface health on the Command Dashboard (design skill, "The three audiences") |

Quality inspector (Q. Fischer) is out of W3 scope — QI capability landed in W2.

## 3. Requirements

Requirement IDs are `URS-W3-NNN`. Each carries: statement, MoSCoW priority, lineage (disposition · golden source · evidence), acceptance criteria (Given/When/Then on the shared fixtures), design conformance where UI-bearing, and dependencies.

State vocabulary (fixed, per CONSOLIDATION.md and the dossier): production-order `exec_state` ∈ {Pending, Accepted, In Progress, Completed, Interrupted, Abandoned, Declined}; recipe `gov_state` ∈ {Draft, Checked, Accepted, Outdated, Declined}; batch `qa_state` ∈ {Quarantined, Released, Blocked}. The unqualified word "status" is never used for these (ADR-004).

### 3.1 Capability area: Planning / MRP (backlog W3-1)

#### URS-W3-001 — Production Plan creation from sales input
**Statement:** The system shall allow the planner to create a Production Plan from sales input (sales orders and/or material requests/forecast), listing finished goods with plan quantities and warehouses.
**Priority:** Must
**Lineage:** Adopt · ERPNext · dossier ch. 3.2 (`production_plan.py`; Production Plan status enum `production_plan.json:302`; MPS/forecast doctypes `manufacturing/doctype/master_production_schedule/`)
**Acceptance criteria:**
- AC-1: Given a sales input demanding 500 kg of RW-CHM-0003 "Rheinol 40 Compound" for FG Lager Süd, When planner P. Krüger creates a Production Plan from that input, Then the plan contains one row: item RW-CHM-0003, planned qty 500 kg, target warehouse FG Lager Süd.
- AC-2: Given the Production Plan from AC-1, When P. Krüger submits it, Then the plan is in a submitted, non-editable form and appears in the planning work queue.
**Design conformance:** Planning screens use the Work Queue → Detail pattern in Desk mode (design skill §"Layout patterns" 1, §"Density modes"); full keyboard path (Enter confirms, Esc cancels, arrow keys move rows — §"Interaction rules"); quantities right-aligned tabular numerals with unit "kg" suffixed (§"Component rules — Forms/Tables"); German-first strings, DD.MM.YYYY dates (§"Content and language").
**Dependencies:** W0-4 (anchor BOM/order entities), W1 exit.

#### URS-W3-002 — BOM explosion including sub-assemblies
**Statement:** The system shall explode the Production Plan through the Accepted recipe (BOM) of each planned item, including sub-assembly levels, to compute component requirements.
**Priority:** Must
**Lineage:** Adopt · ERPNext · dossier ch. 3.2 (`production_plan.py` sub-assembly explosion; capability inventory "Planning / MRP" — High); recipe reference restricted to `gov_state` = Accepted per ADR-006/CDM-04
**Acceptance criteria:**
- AC-1: Given BOM-RW-CHM-0003-001 (Accepted `gov_state`) consuming 20 kg RW-CHM-0001 "Rheinol 40 Basisharz" and 1 kg RW-CHM-0002 "Additiv K7" per 25 kg of RW-CHM-0003, When the plan for 500 kg RW-CHM-0003 is exploded, Then computed requirements are exactly 400 kg RW-CHM-0001 and 20 kg RW-CHM-0002.
- AC-2: Given a BOM for RW-CHM-0003 whose `gov_state` is Draft, When P. Krüger attempts to plan with it, Then the plan refuses the reference and names the rule (only Accepted recipes plannable), the record (the Draft BOM id), and the resolution (accept the recipe or select an Accepted version).
**Design conformance:** The AC-2 refusal is a gate refusal: modal, logged, naming rule/record/resolution — never a dismissable toast (design skill §"Interaction rules — Hard gates look hard").
**Dependencies:** URS-W3-001; W1-4 (recipe governance).

#### URS-W3-003 — MRP netting and material request generation
**Statement:** The system shall net component requirements against ledger on-hand stock (Bin) and open reservations, and generate Material Requests only for net shortages.
**Priority:** Must
**Lineage:** Adopt · ERPNext · dossier ch. 3.2 `production_plan/services/material_request.py:141` (`get_items_for_material_requests` MRP netting); quantity truth is the anchor ledger per ADR-005/CDM-03
**Acceptance criteria:**
- AC-1: Given requirement 400 kg RW-CHM-0001 and BATCH-A-0001 providing 500 kg Released on-hand in RM Lager Nord with no reservations, When netting runs, Then no Material Request row is generated for RW-CHM-0001.
- AC-2: Given requirement 20 kg RW-CHM-0002 and only BATCH-A-0002 on hand with `qa_state` Blocked, When netting runs, Then Blocked stock is not counted as available and a Material Request for 20 kg RW-CHM-0002 is generated (blocking excludes stock from availability per CDM-01 lifecycle, W2-3 scope).
**Dependencies:** URS-W3-002; W2-3 (blocking exclusion — cross-wave dependency, parent to reconcile exact ID).

#### URS-W3-004 — Production order generation from the plan
**Statement:** The system shall generate production orders (anchor Work Order + `exec_state`) from the Production Plan, created in `exec_state` Pending.
**Priority:** Must
**Lineage:** Adopt (anchor) + Absorb (state layer) · ERPNext + Qcadoo semantics · CDM-02/ADR-004; dossier ch. 3.2 Production Plan → Work Order spawning (`work_order.json` link `production_plan`)
**Acceptance criteria:**
- AC-1: Given the submitted plan for 500 kg RW-CHM-0003, When P. Krüger generates orders, Then production order PO-2026-0001 exists for 500 kg RW-CHM-0003 on line LINE-1 with `exec_state` = Pending and its `state_history` records creator and timestamp.
- AC-2: Given PO-2026-0001 in `exec_state` Pending, When it is displayed anywhere in the planning UI, Then the state is shown as a status pill (icon + label + colour) using the exact label "Pending" — no synonyms.
**Design conformance:** Status pill component per design skill §"Component rules — Status pill"; order identifiers (PO-2026-0001) rendered in mono (§"Typography — Identifiers").
**Dependencies:** URS-W3-001; W1-1 (exec_state machine).

### 3.2 Capability area: Finite capacity (backlog W3-2)

#### URS-W3-005 — Line schedules with governed schedule states
**Statement:** The system shall let the planner build per-production-line schedules of accepted orders, with schedule lifecycle Draft → Approved / Rejected matching Qcadoo `ScheduleState` semantics.
**Priority:** Must
**Lineage:** Absorb (partial) · Qcadoo · dossier ch. 3.1 `orders/states/constants/ScheduleState.java:8-24` (DRAFT/APPROVED/REJECTED + transitions); re-implementation, never a code port (implication 1)
**Acceptance criteria:**
- AC-1: Given PO-2026-0001 and PO-2026-0002 in `exec_state` Accepted on line LINE-1, When P. Krüger creates a schedule for LINE-1, Then the schedule is created in state Draft containing both orders with computed start/end times.
- AC-2: Given the Draft schedule, When P. Krüger approves it, Then the schedule state is Approved and the schedule becomes the operative sequence for LINE-1; When P. Krüger rejects a Draft schedule instead, Then it is Rejected and has no operative effect.
- AC-3 (parity): Given the characterization baseline of `ScheduleState.java:8-24`, When the target's allowed schedule transitions are enumerated, Then they equal the baseline set {Draft→Approved, Draft→Rejected} with no additional transitions. Target must match legacy exactly.
**Design conformance:** Schedule board is a Desk-mode professional view — dense, keyboard-navigable, nothing hidden behind hover/progressive disclosure (design skill §"Interaction rules — Nothing hides on desktop"); schedule state as status pill.
**Dependencies:** URS-W3-004; W1-1.

#### URS-W3-006 — Realization-time calculation from TJ/TPZ norms
**Statement:** The system shall compute order/operation realization times from unit production time (TJ) and setup/preparatory time (TPZ) norms per operation and work centre, following Qcadoo realization-time semantics.
**Priority:** Must
**Lineage:** Absorb (partial) · Qcadoo · dossier ch. 3.1 `productionScheduling/OrderRealizationTimeServiceImpl.java` (TJ/TPZ time norms); CDM-08 work-centre `production_line` extension (ADR-010)
**Acceptance criteria:**
- AC-1: Given routing RT-COMPOUND-01 where operation MIX at work centre LINE-1/MIX-01 has TPZ 30 min and TJ 0.6 min/kg, and operation FILL at LINE-1/FILL-01 has TPZ 15 min and TJ 0.3 min/kg, When realization time is computed for PO-2026-0001 (500 kg), Then MIX duration = 30 + 500×0.6 = 330 min and FILL duration = 15 + 500×0.3 = 165 min, and the order realization time equals the routed sequence total (495 min for sequential routing).
- AC-2 (parity): Given the characterization fixtures for `OrderRealizationTimeServiceImpl` (same TJ/TPZ inputs run against the legacy baseline), When the target computes realization times, Then results match the legacy values exactly (to the minute). Target must match legacy exactly.
**Dependencies:** URS-W3-005; W0-6 (characterisation harness), W0-3/CDM-08.

#### URS-W3-007 — Line changeover norms in schedule computation
**Statement:** The system shall apply line changeover norms (time between orders of different products on the same line) when sequencing orders in a line schedule.
**Priority:** Should
**Lineage:** Absorb (partial) · Qcadoo · dossier ch. 3.1 capability inventory "Planning & scheduling" (plugin `mes-plugins-line-changeover-norms`)
**Acceptance criteria:**
- AC-1: Given a changeover norm of 45 min on LINE-1 between RW-CHM-0003 and any other product, When PO-2026-0002 is scheduled immediately after PO-2026-0001 on LINE-1, Then PO-2026-0002's computed start is ≥ PO-2026-0001's end + 45 min.
- AC-2: Given no changeover norm defined for a product pair, When two such orders are sequenced, Then no changeover time is inserted and the schedule notes "no changeover norm" for the transition.
**Dependencies:** URS-W3-005, URS-W3-006.

#### URS-W3-008 — Anchor capacity slot search retained under the schedule layer
**Statement:** The system shall retain the anchor's capacity slot search: with capacity planning enabled, an operation that cannot be placed within the plan window at its work centre's `production_capacity` shall be refused with a capacity error.
**Priority:** Should
**Lineage:** Adopt · ERPNext · dossier ch. 3.2 `work_order/services/operations.py:105-130` (`CapacityError`), `workstation.json` (`production_capacity`)
**Acceptance criteria:**
- AC-1: Given LINE-1/MIX-01 with `production_capacity` = 1 fully booked by PO-2026-0001 for the plan window, When P. Krüger tries to schedule PO-2026-0002's MIX operation in the same window, Then the system refuses with a capacity error naming the work centre (LINE-1/MIX-01), the blocking booking, and the earliest feasible slot as resolution.
**Design conformance:** Capacity refusal presented as a gate refusal — modal, logged, rule/record/resolution (design skill §"Hard gates look hard").
**Dependencies:** URS-W3-005.

#### URS-W3-009 — Constraint-based optimisation (Won't — recorded exclusion)
**Statement:** The system shall NOT include a constraint-based finite-capacity optimiser in W3; scheduling remains norm/slot-based with manual planner sequencing.
**Priority:** Won't (this wave)
**Lineage:** White space · none (absent in all three sources) · dossier §6.2 "Finite capacity scheduling … still no optimiser anywhere", §6.3; build-vs-buy is business decision D4 (`docs/plan/consolidation-project-plan.md` Dependencies D4)
**Acceptance criteria:**
- AC-1: Given the W3 scope baseline, When the delivered scheduling features are audited at wave exit, Then no optimiser component exists and decision record D4 (build vs buy) is documented with a status, so absence is deliberate and traceable rather than an omission.
**Dependencies:** — (records the boundary of URS-W3-005…008).

### 3.3 Capability area: Group-ERP interface (backlog W3-3, W3-4; ADR-002)

#### URS-W3-010 — Orders in (inbound demand)
**Statement:** The system shall accept inbound order demand from the group ERP over the boundary interface and create/maintain corresponding MES demand (sales input to planning), keyed by an external order reference.
**Priority:** Must
**Lineage:** Rebuild (boundary) · none (contract per ADR-002) · ADR-002 "Interface contract: orders in, confirmations out, GL postings out"; external-reference precedent dossier ch. 3.1 `OrderFields.java:48,88` (`externalNumber`/`externalSynchronized`)
**Acceptance criteria:**
- AC-1: Given contract fixture ERP-IN-001 carrying an order for 500 kg RW-CHM-0003 with external reference GRP-SO-77001, When the interface processes it, Then a sales-input record exists in the MES referencing GRP-SO-77001 and is available to Production Plan creation (URS-W3-001).
- AC-2: Given the same fixture ERP-IN-001 delivered a second time (duplicate), When the interface processes it, Then no duplicate demand is created and the duplicate is logged with reference GRP-SO-77001 (idempotency).
- AC-3: Given a fixture with an unknown item code, When processed, Then the message is rejected to an error queue with a machine-readable reason and no partial data is written.
**Dependencies:** URS-W3-019 (contract freeze), external dependency D1 (group-ERP interface availability).

#### URS-W3-011 — Confirmations out (production confirmations)
**Statement:** The system shall emit a production confirmation message to the group ERP when a production order reaches `exec_state` Completed, carrying order reference, produced item, produced quantity, and FG batch identifiers.
**Priority:** Must
**Lineage:** Rebuild (boundary) · none · ADR-002; completion semantics from CDM-02 (`exec_state` Completed requires produced ≥ ordered or explicit shortfall reason)
**Acceptance criteria:**
- AC-1: Given PO-2026-0001 completed with 500 kg RW-CHM-0003 into batch BATCH-C-1001, When `exec_state` transitions to Completed, Then exactly one confirmation message is emitted containing GRP-SO-77001 (if linked), RW-CHM-0003, 500 kg, and BATCH-C-1001, and it validates against the frozen contract schema.
- AC-2: Given the ERP endpoint is unreachable, When the confirmation is emitted, Then it is queued durably and delivered on recovery without loss or duplication, and the interface health surface shows the backlog.
**Dependencies:** W1-1 (exec_state), URS-W3-013.

#### URS-W3-012 — GL postings out (boundary costing/valuation)
**Statement:** The system shall map perpetual-inventory GL postings arising from stock ledger entries to group-ERP account codes via a maintained account map, and emit them over the boundary interface; the MES holds no financial ledger of record.
**Priority:** Must
**Lineage:** Adopt (boundary) · ERPNext · dossier ch. 3.2 `stock_controller.py` (perpetual-inventory GL from SLE), `item.json:387-390` (valuation methods), `stock_ledger.py:1726-1729` (FIFO/LIFO queue); fenced per ADR-002
**Acceptance criteria:**
- AC-1: Given BATCH-C-1001 (500 kg RW-CHM-0003) received into FG Lager Süd at valuation rate 4.20 €/kg, When the manufacture posting is made, Then a GL-posting message of 2,100.00 € debit/credit pair is emitted with FG Lager Süd's mapped group-ERP account codes, validating against the contract schema.
- AC-2: Given a warehouse with no account mapping, When a posting for it arises, Then the posting is held in an unmapped-accounts queue, an alert names the warehouse and the missing map entry, and nothing is emitted until the map is completed.
**Dependencies:** W1-3 (anchor hard stops/valuation), URS-W3-013.

#### URS-W3-013 — Contract fixtures and versioned interface schema
**Statement:** The system shall maintain a versioned, machine-validated interface contract (schemas for orders-in, confirmations-out, GL-postings-out) with a fixture set covering happy path, duplicate, and rejection cases; contract tests shall run in CI.
**Priority:** Must
**Lineage:** Rebuild (boundary) · none · ADR-002 "interface fixtures tested in Wave W3"; wave exit criterion (`docs/waves/W3-planning-boundary.md`)
**Acceptance criteria:**
- AC-1: Given the frozen contract version 1.0, When the fixture suite (≥ 1 happy, ≥ 1 duplicate, ≥ 1 rejection per message type — 9 fixtures minimum) runs in CI, Then all pass and the run is linked from the wave evidence pack.
- AC-2: Given a proposed schema change, When it is not backward-compatible with version 1.0, Then the contract version increments and both versions' fixtures pass during the agreed transition window.
**Dependencies:** URS-W3-010…012; external D1.

#### URS-W3-014 — Interface monitoring, error handling and replay
**Statement:** The system shall provide the business viewer and planner an interface-health surface (message counts, error queue depth, oldest unprocessed message) and allow authorised replay of failed messages with full audit.
**Priority:** Should
**Lineage:** Rebuild (boundary) · none · ADR-002; audit precedent dossier ch. 3.1 §E (state-change audit rows)
**Acceptance criteria:**
- AC-1: Given 1 rejected orders-in message (URS-W3-010 AC-3), When B. Vogel opens the Command Dashboard, Then a plain-language KPI tile ("ERP messages needing attention: 1") drills down to the professional error-queue view showing the message with its rejection reason.
- AC-2: Given the corrected message, When P. Krüger replays it, Then processing succeeds, and the audit log records who replayed, when, and the message reference.
**Design conformance:** Command Dashboard pattern — plain-language KPI tiles drilling into professional queue views (design skill §"Layout patterns" 3); error queue is a dense table with mono message references.
**Dependencies:** URS-W3-010…013.

### 3.4 Capability area: SCADA/OPC-UA adapter (backlog W3-5 — white space, net-new)

#### URS-W3-015 — OPC-UA tracking-event ingestion
**Statement:** The system shall ingest process-control events (operation start/stop, produced quantity counts) from plant equipment via an OPC-UA adapter and attach them to the correct production order and operation as tracking events.
**Priority:** Must
**Lineage:** Rebuild · none (white space) · dossier §6.3 "SCADA/OPC-UA / device connectivity — absent in all three" (searches documented per chapter §G); backlog W3-5
**Acceptance criteria:**
- AC-1: Given the OPC-UA adapter subscribed to LINE-1/MIX-01 tags and PO-2026-0001 In Progress on LINE-1, When the equipment publishes a produced-count event of 25 kg, Then a tracking event of 25 kg is recorded against PO-2026-0001's MIX operation within 5 s, attributed to source "OPC-UA" (not to an operator).
- AC-2: Given an event for a work centre with no order In Progress, When it arrives, Then it is held in an unmatched-events queue for planner disposition and is not silently dropped.
**Dependencies:** W1-7 (operator journey / tracking records), W2-1 (genealogy recording — cross-wave, parent to reconcile).

#### URS-W3-016 — Tag-to-work-centre mapping administration
**Statement:** The system shall let the technologist maintain the mapping of OPC-UA node/tag addresses to work centres (CDM-08) and event types, with validation that each mapped work centre exists.
**Priority:** Must
**Lineage:** Rebuild · none (white space) · dossier §6.3; CDM-08/ADR-010 (Workstation + production_line)
**Acceptance criteria:**
- AC-1: Given T. Schmid maps tag `ns=2;s=Line1.Mix01.ProducedKg` to work centre LINE-1/MIX-01 event type "produced-count", When the mapping is saved, Then events on that tag resolve to LINE-1/MIX-01 (URS-W3-015 AC-1 path).
- AC-2: Given a mapping referencing a non-existent work centre code, When save is attempted, Then save is refused naming the invalid code.
**Design conformance:** Mapping admin is a Desk-mode table with mono tag identifiers (design skill §"Typography — Identifiers", §"Component rules — Tables").
**Dependencies:** URS-W3-015, W0-3.

#### URS-W3-017 — Store-and-forward on link loss
**Statement:** The system shall buffer OPC-UA events during connectivity loss between adapter and MES and deliver them in order on reconnection, flagging late-arriving events with their original equipment timestamp.
**Priority:** Should
**Lineage:** Rebuild · none (white space) · dossier §6.3; backlog W3-5 ("tracking events from process control into production records")
**Acceptance criteria:**
- AC-1: Given a 10-minute adapter-to-MES outage during which LINE-1/MIX-01 publishes 3 produced-count events, When connectivity is restored, Then all 3 events are recorded against PO-2026-0001 in original order with original timestamps and a late-delivery flag.
**Dependencies:** URS-W3-015.

### 3.5 Capability area: Hazmat/regulatory completion (backlog W3-6 — white space, net-new)

#### URS-W3-018 — Shipping/ADR boundary data and label data
**Statement:** The system shall complete hazmat data at the shipping boundary: for items with a hazmat profile (W2-7 scope), the technologist shall maintain ADR transport data (UN number, proper shipping name, ADR class, packing group) and the system shall render dispatch label data for FG batches; dispatch of a hazmat batch without complete ADR data shall be refused.
**Priority:** Must
**Lineage:** Rebuild · none (white space) · dossier §6.3 "Hazmat / regulatory master data … absent in all three"; backlog W3-6; depends on W2-7 (hazmat master data) — CDM-01 `hazmat_profile`
**Acceptance criteria:**
- AC-1: Given RW-CHM-0003's hazmat profile with UN 1263, proper shipping name "FARBE", ADR class 3, packing group III, When W. Braun produces the dispatch label data for BATCH-C-1001 from FG Lager Süd, Then the label output contains UN 1263, "FARBE", class 3, PG III, batch BATCH-C-1001, and net quantity in kg.
- AC-2: Given a hazmat item whose profile lacks a UN number, When dispatch of its batch is attempted, Then the system refuses, naming the rule (ADR data incomplete), the record (the item and missing field), and the resolution (complete the hazmat profile).
**Design conformance:** Refusal per gate-refusal rule (modal, logged, rule/record/resolution); label preview usable in Terminal mode at dispatch stations — 48 px targets, scanner path to select the batch/HU (HU-000123 scan resolves the handling unit) per design skill §"Density modes", §"Scanner is a first-class input".
**Dependencies:** W2-7 (cross-wave), W2-2 (unified batch).

### 3.6 Capability area: External-sync survey & contract freeze (backlog W3-7)

#### URS-W3-019 — Survey and contract-freeze register of existing external syncs
**Statement:** The programme shall produce a register of all existing external synchronisations (all consumers of Qcadoo `externalNumber`/`externalSynchronized` fields; all active ERPNext integrations at Plant C), and each shall be dispositioned (carry across boundary / retire / replace) with its contract frozen before the ERP interface contract (URS-W3-013) is finalised.
**Priority:** Must
**Lineage:** — (survey; no code disposition) · — · dossier ch. 3.1 `OrderFields.java:48,88`; open question §8.2 #6 ("Is there an external WMS/ERP currently connected to any plant … must those interfaces survive consolidation?")
**Acceptance criteria:**
- AC-1: Given the survey is executed at Plants A and C, When the register is published, Then every entry has: system name, direction, data objects, evidence of use (or confirmed unused), and a disposition; and open question §8.2 #6 is marked answered in the programme register.
- AC-2: Given any register entry dispositioned "carry", When the ERP interface contract v1.0 is frozen, Then that entry's requirements are reflected in the contract fixtures (URS-W3-013) — no carried sync without a fixture.
**Dependencies:** blocks URS-W3-010…013 finalisation; W0-5.

### 3.7 Untraceable / deferred

- **Partner-master ownership at the boundary** (are supplier/customer masters owned by group ERP with MES holding references only?) — business decision D5 (`docs/plan/consolidation-project-plan.md`); no legacy evidence determines the answer. Deferred to the D5 sign-off; URS-W3-010's demand model assumes references-only and must be revisited if D5 decides otherwise.
- **Finite-capacity optimiser build-vs-buy** — decision D4; recorded as Won't in URS-W3-009 rather than an invented requirement.

## 4. Non-functional requirements (W3-8)

#### URS-W3-020 — Planning & boundary performance
**Statement:** The system shall meet: schedule-board initial render for a 200-order line schedule ≤ 2 s; UI feedback for every planner action < 100 ms with progress shown on the control for longer operations; scan-to-confirmation at dispatch stations ≤ 300 ms server-confirmed; orders-in fixture message processed end-to-end ≤ 10 s.
**Priority:** Must
**Lineage:** Design skill §"Interaction rules — No dead air" (<100 ms, server-confirmed gated actions), §"Component rules — Tables" (virtualized beyond 200 rows); interface budget derived from URS-W3-010.
**Acceptance criteria:**
- AC-1: Given a LINE-1 schedule of 200 orders, When the board loads, Then first meaningful render ≤ 2 s and the table is virtualized.
- AC-2: Given W. Braun scans HU-000123 at dispatch, When the scan is accepted, Then server-confirmed feedback appears ≤ 300 ms with full-row visual + audible confirmation.

#### URS-W3-021 — Audit and logging of gated and boundary actions
**Statement:** The system shall write an immutable audit record (actor or source system, timestamp, action, record reference, outcome) for: every schedule approval/rejection, every gate refusal (capacity, recipe-governance, hazmat dispatch), every boundary message processed/rejected/replayed, and every OPC-UA-sourced tracking event.
**Priority:** Must
**Lineage:** Absorb · Qcadoo audit precedent (dossier ch. 3.1 §E `orderStateChange.xml:36-47` per-entity state-change audit) + design skill §"Hard gates look hard" ("modal and logged").
**Acceptance criteria:**
- AC-1: Given URS-W3-008 AC-1's capacity refusal, When the audit log is queried for PO-2026-0002, Then a refusal entry exists naming the rule and work centre LINE-1/MIX-01.
- AC-2: Given URS-W3-014 AC-2's replay, When the audit log is queried, Then the replay entry names P. Krüger, the timestamp, and message reference.

#### URS-W3-022 — German-first i18n and locale formats
**Statement:** All W3 UI strings shall be externalized with German as the primary locale; dates shall render DD.MM.YYYY and quantities in kg with locale-correct decimal separators; no string concatenation for translatable text.
**Priority:** Must
**Lineage:** Design skill §"Content and language" ("German-first i18n discipline … DD.MM.YYYY and kg"); precedent dossier ch. 3.1 (locales en/pl/fr/de/cn), ch. 3.2 (`erpnext/locale/de.po`).
**Acceptance criteria:**
- AC-1: Given the locale is de, When the schedule board renders PO-2026-0001's planned start 31.12.2026, Then the date shows as "31.12.2026" and quantity as "500 kg" with German number formatting; state pill labels come from the externalized glossary (no hard-coded English fallbacks in W3 screens — verified by string-extraction lint).

#### URS-W3-023 — Access control for planning and boundary actions
**Statement:** The system shall gate: schedule approval to the planner role; interface replay and account-map maintenance to explicitly authorised roles; tag-mapping administration to the technologist role — with workflow-state-level permissions (per-transition), not only DocType-level rights.
**Priority:** Must
**Lineage:** Absorb · Qcadoo per-transition role semantics (dossier ch. 3.1 §B.2, 151 granular roles incl. per-state-transition; implication 7 role-model levelling) on W1-8's role model.
**Acceptance criteria:**
- AC-1: Given operator O. Weber's role set, When O. Weber attempts to approve the LINE-1 schedule, Then the action is refused and audited; When planner P. Krüger performs it, Then it succeeds.
- AC-2: Given a user with planner but not interface-admin rights, When they attempt message replay, Then it is refused naming the required permission.
**Dependencies:** W1-8.

## 5. Data migration requirements

W3 lands no migrated data. Master data migrated in W0 (W0-5), open batches/genealogy history in W2, backfills in W4 (see URS-W4). The only W3 data obligations are: the frozen interface contract fixtures (URS-W3-013) and the GL account map (URS-W3-012), both created new — reconciliation of the account map is covered by URS-W3-012 AC-2 (unmapped-accounts hold queue).

## 6. Wave exit criteria

Restated from `docs/waves/W3-planning-boundary.md` ("**Exit:** planning journey complete; ERP interface contract tested with fixtures") and decomposed:

| ID | Check | Verifies |
|---|---|---|
| EXIT-W3-1 | Planning journey demonstrably complete end-to-end: sales input GRP-SO-77001 → Production Plan → explosion (400 kg RW-CHM-0001 / 20 kg RW-CHM-0002) → Material Request for shortage → PO-2026-0001 Pending → Approved LINE-1 schedule with TJ/TPZ times and changeover applied | URS-W3-001…008 |
| EXIT-W3-2 | ERP interface contract v1.0 frozen and fixture suite (≥ 9 fixtures across 3 message types) passing in CI, linked from the evidence pack | URS-W3-010…013 |
| EXIT-W3-3 | External-sync register published, all entries dispositioned, open question §8.2 #6 answered; carried syncs have contract fixtures | URS-W3-019 |
| EXIT-W3-4 | SCADA path demonstrated: OPC-UA fixture event recorded against PO-2026-0001 incl. outage replay; unmatched-event queue functioning | URS-W3-015…017 |
| EXIT-W3-5 | Hazmat dispatch demonstrated: BATCH-C-1001 label data correct; incomplete-profile dispatch refused with rule/record/resolution | URS-W3-018 |
| EXIT-W3-6 | NFR evidence: performance measurements (URS-W3-020), audit samples (URS-W3-021), i18n lint pass (URS-W3-022), permission matrix test pass (URS-W3-023) | URS-W3-020…023 |
| EXIT-W3-7 | Won't-scope confirmed: no optimiser shipped; D4 decision record present with status | URS-W3-009 |
