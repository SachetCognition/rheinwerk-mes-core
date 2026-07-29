# Target Capability Model (Stage 2.1)

**Input:** as-is 30-capability model in `docs/10-discovery/dossier/production-systems-dossier.md` (Part 4), fit-gap (Part 6) and consolidation implications (Part 7).
**Purpose:** turn the as-is map (describing three systems) into the target model (describing the consolidated Rheinwerk MES plus the group-ERP boundary).

Three adjustments were applied to the dossier taxonomy:

1. **White-space promotion** — chemicals capabilities absent in all three sources (dossier §6.3) become first-class target capabilities: ISA-88 recipe management, Certificate of Analysis generation, hazmat/regulatory data handling, plus e-signatures and SCADA/OPC-UA connectivity.
2. **Retire-only marks** — capabilities present in a source but not required in the target. Final confirmation needs the operational overlay + business sign-off; candidates are marked `Retire? (Q#)` referencing the open questions register below.
3. **ERP-boundary marks** — capabilities that may belong to the group ERP (ADR-002): marked `Boundary`, feeding the one-app-vs-two decision.

Target homes: **Anchor** (ERPNext substrate as shipped), **Integrity** (absorbed semantics re-implemented as the integrity layer), **Chemicals** (net-new chemicals layer), **Boundary** (interface to group ERP), **Retire** (not carried).

## Target capability model

| # | Target capability (ISA-95 aligned area) | Origin | Target home | Notes |
|---|---|---|---|---|
| **Production execution (ISA-95 L3 — Production operations)** | | | | |
| T1 | Production order lifecycle (explicit, role-gated state machine) | As-is #1 | Integrity | Workflow layered over Work Order; Qcadoo semantics |
| T2 | Execution gating / hard stops | As-is #2 | Integrity | Union of Qcadoo gates + anchor stops |
| T3 | Shop-floor execution & recording (job cards, time logs) | As-is #3, #4 | Anchor | ERPNext Shop Floor / Job Card |
| T4 | Labour & shift tracking | As-is #4 (+Qcadoo shifts) | Anchor | Qcadoo wage groups: Retire? (Q1) |
| **Recipe / product definition (ISA-95 product definition management)** | | | | |
| T5 | BOM & routing definition | As-is #5 | Anchor | ERPNext BOM + Routing |
| T6 | Recipe lifecycle governance (approval, immutability, in-use locks) | As-is #6 | Integrity | Qcadoo technology-state semantics |
| T7 | **ISA-88 batch recipe management** (master/control recipes, phases, formula scaling) | White space | Chemicals | First-class; dossier §6.3 |
| **Traceability (ISA-95 product tracking & genealogy)** | | | | |
| T8 | Batch/lot master data (unified batch object) | As-is #8 | Integrity | Canonical entity CDM-01; beyond all three sources |
| T9 | Batch genealogy (system-of-record) | As-is #9 | Integrity | Qcadoo TrackingRecord semantics |
| T10 | Batch QA state & quarantine (blocking with propagation + picking exclusion) | As-is #10 | Integrity | Absorbed + extended (implication 3) |
| **Quality (ISA-95 quality operations)** | | | | |
| T11 | Quality inspection engine (typed, parametric, gated) | As-is #11, #12 | Anchor | ERPNext engine |
| T12 | **Certificate of Analysis generation** | White space | Chemicals | Generated from inspection results per batch |
| T13 | **E-signatures on compliance-critical transitions** | White space | Chemicals | 21 CFR Part 11-style; scope decision Q2 |
| **Inventory / warehouse (ISA-95 material handling)** | | | | |
| T14 | Warehouse structure incl. pallets/handling units & storage locations | As-is #14 | Integrity | Physical-fidelity extension of anchor warehouse tree |
| T15 | FEFO/FIFO picking & disposal algorithms | As-is #15 | Integrity | Per-warehouse algorithm; expiry policy decision (implication 6) |
| T16 | Stock reservations (order- and document-level) | As-is #16 | Anchor + Integrity | Anchor SRE + absorbed draft-reservation semantics |
| T17 | Inventory valuation & costing | As-is #17 | Boundary | GL postings out to group ERP (ADR-002); valuation stays for stock integrity |
| **Planning (ISA-95 detailed production scheduling)** | | | | |
| T18 | Production planning / MRP | As-is #18 | Anchor | Production Plan/MPS; demand signal from group ERP — Boundary input |
| T19 | Finite-capacity scheduling (line schedules, changeover norms) | As-is #19 | Integrity | Qcadoo norms; optimiser remains white space (buy decision Q3) |
| **Master data & platform** | | | | |
| T20 | Item/product, work-centre, partner master data | As-is #20 | Anchor | Partner (supplier/customer) masters: Boundary — owned by group ERP (Q4) |
| T21 | UoM & conversions | As-is #21 | Anchor | |
| T22 | **Hazmat / regulatory master data** (UN numbers, SDS, storage classes, ADR) | White space | Chemicals | On Item + Batch |
| T23 | **SCADA / OPC-UA / device connectivity** | White space | Chemicals | Adapter service; W3 |
| T24 | External integration (group ERP, WMS) | As-is #24 | Boundary | Orders in, confirmations + GL postings out |
| T25 | Reporting & analytics | As-is #25 | Anchor | Regulatory-required legacy reports to be confirmed (Q5) |
| T26 | Maintenance management (CMMS) | As-is #26 | Integrity | Qcadoo depth; scope confirmation Q6 |
| T27 | Audit trail & versioning | As-is #27 | Anchor | `track_changes` + immutable ledgers; e-sign in T13 |
| T28 | Multi-plant operation | As-is #28 | Anchor | Multi-company/Company Restriction |
| T29 | Localisation (de + en mandatory) | As-is #29 | Anchor | |
| T30 | RBAC incl. workflow-state-level permissions | As-is #30 | Anchor + Integrity | Implication 7 |
| **Retire-only (present in sources, not carried)** | | | | |
| R1 | Finance/accounting beyond stock GL (OFBiz accounting, ERPNext accounts as books of record) | As-is (source-only) | Retire → group ERP | ADR-002 |
| R2 | Buying/procurement & selling/CRM apps | As-is (source-only) | Retire → group ERP | Procurement-adjacent inventory receipt stays (Boundary) |
| R3 | OFBiz non-manufacturing suite (party portals, e-commerce hooks, content mgmt) | As-is (source-only) | Retire | `plugins/` empty at analysed commit |
| R4 | Qcadoo customer-specific plugins/toggles (e.g. `ziepiwowarski`) | As-is (source-only) | Retire? (Q7) | Confirm inactive in Plant A |
| R5 | Qcadoo per-language DB dump variants (pl/fr/cn schema dumps) | As-is (source-only) | Retire | Superseded by anchor i18n |

## One-app-vs-two feed (Boundary summary)

Boundary-marked capabilities (T17 valuation postings, T18 demand input, T20 partner masters, T24 integration, R1/R2) all sit on the MES↔group-ERP seam. Nothing in the target model requires a second *MES-side* application: the recorded one-app outcome (ADR-002) stands, with the group ERP as the second system across the boundary.

## Open questions register (Stage 2 additions)

| Q# | Question | Blocks |
|---|---|---|
| Q1 | Are Qcadoo wage groups/labour-cost norms used for payroll or only costing? | T4 retire scope |
| Q2 | Which transitions legally require e-signatures (vs audit trail only)? | T13 scope |
| Q3 | Build vs buy for finite-capacity optimisation? | T19 |
| Q4 | Are supplier/customer masters owned by group ERP (MES holds references only)? | T20 boundary |
| Q5 | Which legacy reports are regulatory-required? | T25 |
| Q6 | Is CMMS in MES scope or does a group EAM exist? | T26 |
| Q7 | Are customer-specific Qcadoo toggles active in Plant A? | R4 |
