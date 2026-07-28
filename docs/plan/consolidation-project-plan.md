# Consolidation Implementation Project Plan (Stage 4)

High-level plan of record for the Rheinwerk Chemie MES consolidation programme. Every row traces to a wave backlog item in `docs/waves/` or a RAID source in the dossier (`docs/dossier/production-systems-dossier.md`) and target model (`docs/target-model/`). **No calendar dates** — sequencing is relative (sprint numbers only). Identical content is maintained in `consolidation-project-plan.xlsx`.

> All effort estimates are indicative T-shirt sizes, not commitments. Durations assume 2-week sprints and one blended team working the waves sequentially (W0→W4); no calendar dates are implied — sequencing is by sprint number only.

## Summary

### Wave sequence

| Wave | Theme | Entry criteria | Exit criteria | Items | Indicative duration |
|---|---|---|---|---|---|
| W0 | Foundation: scaffold, canonical entities, migration tooling, characterisation harness | Dossier v1.0 committed; target model + dispositions confirmed | canonical entities live; master data from all three sources round-trips; regression floor executing | 8 | 3 sprints |
| W1 | Production core: order state machine, gating, recipe governance, warehouse fidelity base | W0 exit (M0) achieved | planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | 10 | 5 sprints |
| W2 | Traceability & quality: genealogy, blocking, QI, CoA, ISA-88, hazmat | W1 exit (M1) achieved | full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | 10 | 5 sprints |
| W3 | Planning & boundary: MRP, finite capacity, ERP interface, SCADA/OPC-UA | W2 exit (M2) achieved; group-ERP interface contract available | planning journey complete; ERP interface contract tested with fixtures | 7 | 4 sprints |
| W4 | Cutover & decommission: per-plant cutover, backfill, legacy archival | W3 exit (M3) achieved; open questions §8.2 #2/#3/#7 answered | all personas on target; decommission complete | 7 | 3 sprints |

Total indicative duration: **20 sprints** (~40 weeks) with one blended team; waves are sequential per `docs/waves/README.md`.

### Milestones

| Milestone | Name | Relative timing | Criterion |
|---|---|---|---|
| M0 | Foundation exit | End of sprint 3 | Canonical entities live; master data from all three sources round-trips; regression floor executing |
| M1 | Production core exit | End of sprint 8 | Planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented |
| M2 | Traceability & quality exit | End of sprint 13 | Full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional |
| M3 | Planning & boundary exit | End of sprint 17 | Planning journey complete; ERP interface contract tested with fixtures |
| M4 | Decommission complete | End of sprint 20 | All personas on target; legacy systems read-only then archived; decommission evidence pack signed off |

## Plan detail (one row per backlog item)

### Wave W0 — Foundation

| ID | Wave | Workstream | Task | Disposition / golden source | Effort (indicative) | Dependencies | Milestone / exit criterion | Risks / open questions |
|---|---|---|---|---|---|---|---|---|
| W0-1 | W0 | Platform | Scaffold Frappe app `rheinwerk_mes` with module skeletons and CI (lint + test runner) | Adopt (ERPNext substrate) | M (indicative) | — | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | — |
| W0-2 | W0 | Platform | Canonical Item/Product master + UoM conversions, with field mapping from Qcadoo `product` model, ERPNext `Item`, OFBiz `Product` | Adopt ERPNext master data | M (indicative) | W0-1 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | — |
| W0-3 | W0 | Platform | Canonical Work Centre entity (map: Qcadoo workstation/productionLine, ERPNext Workstation, OFBiz FixedAsset machine group) | Adopt ERPNext Workstation | S (indicative) | W0-1 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | — |
| W0-4 | W0 | Platform | Canonical BOM/recipe & production-order entities (anchor DocTypes, no forks) | Adopt ERPNext BOM/Work Order | M (indicative) | W0-1, W0-2 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | Implication 1 (no anchor forks) |
| W0-5 | W0 | Data Migration | Master-data migration tooling: extractors for Qcadoo PostgreSQL schema, ERPNext DocTypes, OFBiz entity XML/derby exports; round-trip fixtures for all three | — (migration tooling) | L (indicative) | W0-2, W0-3, W0-4 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | Implication 4 (data-model migration, not copy) |
| W0-6 | W0 | Platform | Characterisation-test harness: encode Qcadoo order gating (`OrderStateValidationService`), technology validators, FEFO picking order as executable parity contracts | Absorb (Qcadoo semantics) | L (indicative) | W0-1 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | Implication 1 (re-implementation, never a code port) |
| W0-7 | W0 | Platform | Evidence-pack generator: wave-exit report linking backlog items → dossier findings → code/tests | — | S (indicative) | W0-1 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | — |
| W0-8 | W0 | Platform | Decide + record naming/numbering scheme (Qcadoo DB-trigger sequences vs ERPNext naming series) | Adopt ERPNext naming series | S (indicative) | W0-2, W0-4 | M0: canonical entities live; master data from all three sources round-trips; regression floor executing | — |

### Wave W1 — Production core

| ID | Wave | Workstream | Task | Disposition / golden source | Effort (indicative) | Dependencies | Milestone / exit criterion | Risks / open questions |
|---|---|---|---|---|---|---|---|---|
| W1-1 | W1 | Execution & Gating | Explicit production-order state machine layered over Work Order (pending/accepted/inProgress/completed/interrupted/abandoned/declined semantics) as Frappe workflow + hooks — never forking the anchor DocType | Absorb Qcadoo | L (indicative) | W0-4, W0-6 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 1 (state-machine reconciliation) |
| W1-2 | W1 | Execution & Gating | Execution gating hooks: accept requires dates/line/technology; complete requires recorded output > 0; material-availability gate on release | Absorb Qcadoo | L (indicative) | W1-1, W0-6 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 1; §8.2 Q1 (Plant C settings change gating behaviour) |
| W1-3 | W1 | Execution & Gating | Keep/verify anchor hard stops: over-production errors, stopped-WO freeze, closed-terminal, expired-batch throw | Adopt ERPNext | S (indicative) | W0-4 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | §8.2 Q1 (inspection severity / settings) |
| W1-4 | W1 | Recipe Governance | Recipe governance workflow on BOM/Routing: draft→checked→accepted→outdated with structural validators (tree completeness, unit match, in-use lock) | Absorb Qcadoo | L (indicative) | W0-4, W0-6 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 5 (governance-free BOM; BOM+routing split mismatch) |
| W1-5 | W1 | Warehouse & Inventory | Warehouse physical fidelity base: pallet/handling-unit + storage-location DocTypes; per-warehouse disposal algorithm (FIFO/LIFO/FEFO/LEFO) | Absorb Qcadoo | XL (indicative) | W0-2, W0-6 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 4 (no pallet/handling-unit object in anchor) |
| W1-6 | W1 | Warehouse & Inventory | Draft-document stock reservations semantics reconciled with Stock Reservation Entry | Absorb Qcadoo + Adopt ERPNext | M (indicative) | W1-5 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | — |
| W1-7 | W1 | Execution & Gating | Shop-floor operator journey on ERPNext Shop Floor/Job Cards incl. pause/resume and time logs | Adopt ERPNext | M (indicative) | W1-1 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | — |
| W1-8 | W1 | Platform | Role model: workflow-state-level permissions expressing Qcadoo's per-transition roles in Frappe RBAC | Absorb Qcadoo semantics | M (indicative) | W1-1, W1-4 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 7 (role-model levelling, 151 roles) |
| W1-9 | W1 | Warehouse & Inventory | Expiry-enforcement policy decision (hard stop vs FEFO-advisory) recorded with business sign-off + characterisation deltas | Decision | S (indicative) | W1-5 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Implication 6 (estate-wide expiry policy; changes Plant A behaviour) |
| W1-10 | W1 | Execution & Gating | Characterisation-vs-behaviour choices documented per gate (parity or intentional divergence) | — | S (indicative) | W0-6, W1-2, W1-4, W1-9 | M1: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented | Wave exit criterion |

### Wave W2 — Traceability & quality

| ID | Wave | Workstream | Task | Disposition / golden source | Effort (indicative) | Dependencies | Milestone / exit criterion | Risks / open questions |
|---|---|---|---|---|---|---|---|---|
| W2-1 | W2 | Traceability & Quality | Genealogy object model as system-of-record: Batch DocType extensions + Tracking Record (produced batch ↔ used batches) with forward/backward tree browsing | Absorb Qcadoo | L (indicative) | W1-1 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | §8.2 Q2 (genealogy population completeness at Plant A) |
| W2-2 | W2 | Traceability & Quality | Unified batch object: identity + QA state (released/quarantined/blocked) + expiry + genealogy links — collapsing Qcadoo's dual model and ERPNext's stateless Batch | Absorb + extend | L (indicative) | W2-1 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 2 (two batch models must become one); assumption A6 |
| W2-3 | W2 | Traceability & Quality | Batch blocking/quarantine with propagation through genealogy trees and exclusion from picking | Absorb + extend | L (indicative) | W2-2 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 3 (propagation exceeds every current implementation) |
| W2-4 | W2 | Traceability & Quality | Adopt Quality Inspection engine (typed inspections, parametric readings, templates) and wire QI gates to the W1 state machine | Adopt ERPNext | M (indicative) | W1-1 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | §8.2 Q1 (inspection severity setting) |
| W2-5 | W2 | Traceability & Quality | Certificates of Analysis: generate CoA from inspection results per batch (white space — net-new) | Rebuild | M (indicative) | W2-4 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 8 (white space on critical path) |
| W2-6 | W2 | Chemicals Compliance | ISA-88 batch recipes: unit procedures/phases + recipe scaling over BOM/Routing (white space — net-new) | Rebuild | XL (indicative) | W1-4 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 8 |
| W2-7 | W2 | Chemicals Compliance | Hazmat/regulatory master data (UN numbers, SDS references, storage classes) on Item/Batch (white space — net-new; completes in W3) | Rebuild | M (indicative) | W0-2 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 8 |
| W2-8 | W2 | Warehouse & Inventory | Warehouse fidelity completion: quarantine locations, pallet balances, stocktaking/repacking journeys | Absorb Qcadoo | L (indicative) | W1-5, W2-3 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | — |
| W2-9 | W2 | Traceability & Quality | Multi-level trace demo: acceptance test proving full forward + backward trace incl. blocked-batch propagation | — (wave exit) | M (indicative) | W2-1, W2-2, W2-3 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Wave exit criterion |
| W2-10 | W2 | Chemicals Compliance | E-signature decision for compliance-critical transitions (no legacy precedent — white space) | Decision / Rebuild | S (indicative) | W1-1, W1-4 | M2: full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional | Implication 8; target-model Q2 (which transitions legally require e-signatures) |

### Wave W3 — Planning & boundary

| ID | Wave | Workstream | Task | Disposition / golden source | Effort (indicative) | Dependencies | Milestone / exit criterion | Risks / open questions |
|---|---|---|---|---|---|---|---|---|
| W3-1 | W3 | Planning & Scheduling | Production Plan/MRP journey (sales input → explosion → material requests → orders) on anchor | Adopt ERPNext | M (indicative) | W0-4, W1-1 | M3: planning journey complete; ERP interface contract tested with fixtures | — |
| W3-2 | W3 | Planning & Scheduling | Finite-capacity layer: line schedules, changeover norms, TJ/TPZ-style realization times over anchor slot search | Absorb Qcadoo (partial) | L (indicative) | W3-1, W1-1 | M3: planning journey complete; ERP interface contract tested with fixtures | Implication 8 (optimiser is white space); target-model Q3 (build vs buy) |
| W3-3 | W3 | Integration & Boundary | Group-ERP interface: orders in, confirmations out, GL postings out; contract fixtures + tests | Rebuild (boundary) | XL (indicative) | W1-1, W3-4, W3-7 | M3: planning journey complete; ERP interface contract tested with fixtures | External dependency: group-ERP interface availability; target-model Q4 (partner-master ownership) |
| W3-4 | W3 | Integration & Boundary | Costing/valuation at the boundary: perpetual-inventory GL postings mapped to group ERP accounts | Adopt ERPNext (boundary) | M (indicative) | W0-2, W1-3 | M3: planning journey complete; ERP interface contract tested with fixtures | — |
| W3-5 | W3 | Integration & Boundary | SCADA/OPC-UA adapter (white space — net-new): tracking events from process control into production records | Rebuild | XL (indicative) | W1-7, W2-1 | M3: planning journey complete; ERP interface contract tested with fixtures | Implication 8 |
| W3-6 | W3 | Chemicals Compliance | Hazmat/regulatory completion: shipping/ADR data at the boundary, label data | Rebuild | M (indicative) | W2-7 | M3: planning journey complete; ERP interface contract tested with fixtures | Implication 8 |
| W3-7 | W3 | Integration & Boundary | Survey + contract-freeze of existing external syncs (Qcadoo `externalNumber/externalSynchronized` consumers, ERPNext integrations) | — (survey) | S (indicative) | W0-5 | M3: planning journey complete; ERP interface contract tested with fixtures | §8.2 Q6 (external WMS/ERP connections must be confirmed) |

### Wave W4 — Cutover & decommission

| ID | Wave | Workstream | Task | Disposition / golden source | Effort (indicative) | Dependencies | Milestone / exit criterion | Risks / open questions |
|---|---|---|---|---|---|---|---|---|
| W4-1 | W4 | Cutover | Per-plant cutover runbooks by journey (Plant A Qcadoo, Plant B OFBiz, Plant C legacy ERPNext instance) | — (runbooks) | M (indicative) | W1-10, W2-9, W3-3 | M4: all personas on target; decommission complete | §8.2 Q7 (Plant B open production runs / WIP at cutover) |
| W4-2 | W4 | Data Migration | Plant A data backfill: decompose lot-level `Resource` rows into target batch/bundle/bin representation preserving pallet/location/expiry/price | Absorb migration | L (indicative) | W0-5, W1-5, W2-2 | M4: all personas on target; decommission complete | Implication 4 |
| W4-3 | W4 | Data Migration | Plant B backfill: parties/products/inventory balances/open production runs from OFBiz; record genealogy trace-boundary date for optional-lot history | Retire OFBiz | L (indicative) | W0-5, W2-2, W4-1 | M4: all personas on target; decommission complete | Implication 9 (incomplete backfilled genealogy); §8.2 Q3 (lot coverage), Q7 (open WIP) |
| W4-4 | W4 | Data Migration | Plant A genealogy backfill from TrackingRecords incl. archived (`arch_*`) orders | Absorb migration | L (indicative) | W0-5, W2-1 | M4: all personas on target; decommission complete | §8.2 Q2 (genealogy population completeness) |
| W4-5 | W4 | Cutover | Legacy read-only period: freeze legacy writes, keep query access; then archive | — | S (indicative) | W4-2, W4-3, W4-4 | M4: all personas on target; decommission complete | — |
| W4-6 | W4 | Cutover | Archive Qcadoo build artefacts + `nexus.qcadoo.org` snapshot dependencies before decommission (build unreproducibility risk) | — | S (indicative) | — (start early, independent of other W4 items) | M4: all personas on target; decommission complete | Implication 10 (unreproducible build chain — archive early) |
| W4-7 | W4 | Cutover | Decommission evidence pack: per-plant persona sign-off, data-reconciliation reports, trace-boundary register | — (wave exit) | M (indicative) | W4-5, W4-6 | M4: all personas on target; decommission complete | Wave exit criterion |

## RAID

### Risks (from dossier Part 7 consolidation implications)

| # | Risk | Source | Wave(s) affected |
|---|---|---|---|
| R1 | State-machine reconciliation is unavoidable: workflow must layer over anchor derived statuses without forking DocTypes; absorbed gates are hook re-implementations with characterisation tests as parity contract | Dossier §7 implication 1 | W0/W1 |
| R2 | Two batch models must become one; none of the three systems provides identity + QA state + expiry + genealogy links today | Dossier §7 implication 2 | W2 |
| R3 | Quarantine semantics exceed every current implementation (propagation through genealogy trees + picking exclusion) | Dossier §7 implication 3 | W2 |
| R4 | Physical-fidelity migration is a data-model migration, not a data copy; pallet/handling-unit object missing from anchor | Dossier §7 implication 4 | W1/W4 |
| R5 | Recipe governance must be grafted onto a governance-free BOM; Qcadoo unifies BOM+routing while anchor splits them | Dossier §7 implication 5 | W1 |
| R6 | Expiry enforcement policy must be decided estate-wide; harmonising to stricter rule changes Plant A shop-floor behaviour | Dossier §7 implication 6 | W1 |
| R7 | Role-model levelling: per-transition roles (151 in Qcadoo) require workflow-state-level permissions | Dossier §7 implication 7 | W1 |
| R8 | All six white-space capabilities (ISA-88, CoA, hazmat, SCADA, e-signatures, finite-capacity optimisation) are net-new build/buy on the chemicals critical path | Dossier §7 implication 8 | W2/W3 |
| R9 | OFBiz retirement: Plant B optional-lot history makes backfilled genealogy incomplete; trace-boundary date must be recorded and communicated | Dossier §7 implication 9 | W4 |
| R10 | Plant A platform risk bounds the timeline: Java 8/Spring-XML with snapshot dependencies from nexus.qcadoo.org — unreproducible build chain; archive artefacts early | Dossier §7 implication 10 | W4 (act early) |

### Assumptions (from dossier §8.1)

| # | Assumption | Source |
|---|---|---|
| A1 | The analysed commits are the estate baselines (Plant A = Chem_mes@81d6bb5, Plant B = VM_ofbiz-framework@ecf2990, Plant C = Chem_erpnext@31e7970); plant-specific deltas beyond rebranding are absent from source | Dossier §8.1 A1 |
| A2 | Shipped capability ≈ operated capability; settings-dependent behaviour assessed as capability, not as operated policy | Dossier §8.1 A2 |
| A3 | OFBiz optional plugins (REST, BIRT, e-commerce) are out of estate because plugins/ is empty at the analysed commit | Dossier §8.1 A3 |
| A4 | Scoring weights follow ADR-001 (functional 35 / data model 20 / health 20 / extensibility 15 / UX 10) | Dossier §8.1 A4 |
| A5 | ERP-boundary capabilities (finance, buying, selling) are out of MES scope per ADR-002; compared only at boundary level | Dossier §8.1 A5 |
| A6 | Qcadoo genealogy Batch and warehouse Resource.batch refer to the same physical lots in Plant A operations (linkage by convention; needs operational confirmation) | Dossier §8.1 A6 |

### Issues

| # | Issue | Status |
|---|---|---|
| — | None recorded yet (plan of record; issues register opens at W0 start) | — |

### Dependencies (external)

| # | Dependency | Source | Needed by |
|---|---|---|---|
| D1 | Group-ERP interface availability (orders in, confirmations out, GL postings out) — external contract needed before W3-3 can be fixture-tested | External / group ERP | W3 |
| D2 | Business sign-off Q1: Qcadoo wage groups/labour-cost norms used for payroll or only costing? | target-capability-model Q1 | W1 (T4 retire scope) |
| D3 | Business sign-off Q2: which transitions legally require e-signatures (vs audit trail only)? | target-capability-model Q2 | W2 (W2-10) |
| D4 | Business sign-off Q3: build vs buy for finite-capacity optimisation? | target-capability-model Q3 | W3 (W3-2) |
| D5 | Business sign-off Q4: are supplier/customer masters owned by group ERP (MES holds references only)? | target-capability-model Q4 | W3 (W3-3) |
| D6 | Business sign-off Q5: which legacy reports are regulatory-required? | target-capability-model Q5 | W1–W3 reporting scope |
| D7 | Business sign-off Q6: is CMMS in MES scope or does a group EAM exist? | target-capability-model Q6 | W3 |
| D8 | Business sign-off Q7: are customer-specific Qcadoo toggles active in Plant A? | target-capability-model Q7 | W1 |

### Open questions register (dossier §8.2)

Open questions §8.2 #1–#7 (plant settings, genealogy completeness, Plant B lot coverage, Qcadoo toggles, regulatory reports, external syncs, Plant B WIP) must be answered before the wave that depends on them exits (cross-wave rule 3, `docs/waves/README.md`). They are referenced per row in the plan detail above.
