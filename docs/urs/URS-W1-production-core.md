# URS W1 — Production Core

**Rheinwerk MES Consolidation — User Requirements Specification**
Wave: W1 (Production Core) · Source backlog: `docs/waves/W1-production-core.md` (W1-1…W1-10) · Status: Draft for review

---

## 1. Purpose & scope

Wave W1 delivers the production core: the explicit production-order `exec_state` machine layered over the anchor Work Order, execution gating hooks, verification of anchor hard stops, the recipe governance workflow (`gov_state`) on BOM/Routing, the warehouse physical-fidelity base (Handling Unit, Storage Location, per-warehouse disposal algorithms), draft-document reservation semantics reconciled with Stock Reservation Entry, the shop-floor operator journey on Job Cards, workflow-state-level role permissions, the estate-wide expiry-enforcement policy decision, and the per-gate characterisation-vs-behaviour record. W1 exit: planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented (`docs/waves/W1-production-core.md`).

**Out of scope for W1** (later waves — listed so scope creep is visible):

- Batch genealogy system-of-record, unified Batch object with `qa_state` workflow, blocking/quarantine propagation, Quality Inspection wiring, CoA, ISA-88, hazmat — **W2**. W1 references batch expiry data for FEFO/expiry gating but does not deliver the Batch `qa_state` workflow.
- Warehouse fidelity completion (quarantine locations, pallet balances, stocktaking/repacking journeys) — **W2** (W2-8).
- Planning/MRP journey, finite capacity, ERP boundary interface, SCADA — **W3**.
- Open-batch/genealogy/history data migration — **W2/W4**. W1 lands **no migrated data**; it consumes W0 master data and fixtures.

## 2. Personas in scope

From the dossier role model (ch. 3.1 §B.2; ch. 3.2 personas/roles):

| Persona | Fixture name | W1 relevance | Evidence |
|---|---|---|---|
| Planner | P. Krüger | Creates, accepts, declines, releases production orders | dossier ch. 3.1 §B.2 (production planner / supervisor roles); ch. 3.2 `Manufacturing User` on Work Order |
| Shop-floor operator | O. Weber | Executes job cards, records output, pause/resume | dossier ch. 3.2 (`job_card.py:1280-1397`); ch. 3.1 production tracking roles |
| Technologist | T. Schmid | Authors and progresses recipes through governance | dossier ch. 3.1 §B.2 (technology roles); ch. 3.2 `Manufacturing Manager` on BOM |
| Warehouse clerk | W. Braun | Manages handling units, storage locations, issues stock, reservations | dossier ch. 3.1 §B.2 (warehouse operator roles incl. `ROLE_DOCUMENTS_STATES_ACCEPT`) |
| Business viewer | B. Vogel | Reads order progress and the characterisation-choice record | dossier §6.2 platform-substrate row |

Quality inspector (Q. Fischer) enters scope in W2.

## 3. Requirements

### 3.1 Production-order state machine (W1-1)

#### URS-W1-001 — Explicit `exec_state` workflow on Work Order

The system shall provide the user-owned, role-gated `exec_state` workflow (Pending, Accepted, In Progress, Completed, Interrupted, Abandoned, Declined) as a Frappe workflow + hooks layered over the anchor Work Order, never forking the anchor DocType, so that the planner and operator own order state explicitly rather than deriving it from postings.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `orders/states/constants/OrderState.java:31-81`; ADR-004 / CDM-02; dossier §7 implication 1
- **Acceptance criteria:**
  - **AC-1** Given production order PO-2026-0001 (500 kg RW-CHM-0003 on LINE-1) is newly created, When P. Krüger opens it, Then `exec_state` = Pending.
  - **AC-2** Given PO-2026-0001 in Pending with dates, line and Accepted recipe set, When P. Krüger transitions it, Then `exec_state` = Accepted.
  - **AC-3** Given PO-2026-0001 in In Progress, When O. Weber interrupts it, Then `exec_state` = Interrupted, and a subsequent resume returns it to In Progress.
- **Design conformance:** `exec_state` renders as a status pill (icon + label + colour, design skill §"Component rules"); state names use the exact glossary vocabulary (§"Interaction rules — State names are law"); order identifiers in mono (§"Typography").
- **Dependencies:** W0 exit (URS-W0-007, URS-W0-012).

#### URS-W1-002 — Legal transition enforcement

The system shall permit only the legal `exec_state` transitions (Pending→Accepted/In Progress/Declined; Accepted→In Progress/Declined; In Progress→Completed/Interrupted/Abandoned; Interrupted→In Progress/Abandoned; Completed, Declined, Abandoned terminal) and refuse all others, matching the Qcadoo `canChangeTo` transition set exactly.

- **Priority:** Must
- **Lineage:** Absorb (exact parity) · Qcadoo · `OrderState.java:54-81` (illegal state jumps rejected); dossier ch. 3.1 §C.2 order state diagram
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0002 in Completed, When any transition is attempted, Then it is refused (terminal state).
  - **AC-2** Given PO-2026-0001 in Pending, When a direct transition to Completed is attempted, Then it is refused with a message naming the illegal transition.
  - **AC-3** Given the characterisation harness order-transition contract (URS-W0-012), When it runs against the target implementation, Then every legal/illegal transition assertion passes (parity).
- **Dependencies:** URS-W1-001.

#### URS-W1-003 — State-change audit (`state_history`)

The system shall record every `exec_state` transition in the `state_history` child table with state, user, timestamp, and reason (reason mandatory for Declined, Abandoned, Interrupted), equivalent to Qcadoo's order state-change audit entity.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `orders/model/orderStateChange.xml:36-47`; `orders/model/reasonTypeOfChangingOrderState.xml`; CDM-02 `state_history`
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 transitions Pending→Accepted→In Progress, When the `state_history` is read, Then it contains two rows with the acting users (P. Krüger, then O. Weber) and timestamps in order.
  - **AC-2** Given PO-2026-0002 in Pending, When P. Krüger declines it without a reason, Then the transition is refused; When she supplies reason "Kunde storniert", Then it succeeds and the reason is stored.
- **Dependencies:** URS-W1-001.

#### URS-W1-004 — Reconciliation with anchor-derived status; no unqualified "status"

The system shall reconcile `exec_state` with the anchor Work Order's posting-derived status via hooks — accepting requires anchor submit; completing requires produced ≥ ordered or an explicit shortfall reason — and shall never expose the unqualified word "status" in canonical `rheinwerk_mes` interfaces (fields are `exec_state`, `qa_state`, `gov_state`).

- **Priority:** Must
- **Lineage:** Absorb + Adopt reconciliation · Qcadoo semantics over ERPNext anchor · CDM-02 semantics paragraph; ADR-004 decision ("the unqualified word 'status' is banned"); dossier §5.2 production-order row (High mismatch)
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 with the anchor Work Order in Draft (docstatus 0), When acceptance is attempted, Then it is refused until the anchor document is submitted.
  - **AC-2** Given PO-2026-0001 In Progress with produced quantity 480 kg of 500 kg, When completion is attempted without a shortfall reason, Then it is refused; with shortfall reason "Ausschuss Mischvorgang", Then it completes and the reason is stored in `state_history`.
  - **AC-3** Given the `rheinwerk_mes` field and label catalogue, When scanned for an unqualified field/label "status" on canonical DocTypes and screens, Then zero occurrences are found.
- **Dependencies:** URS-W1-001, URS-W1-003.

### 3.2 Execution gating hooks (W1-2)

#### URS-W1-005 — Acceptance gate: dates, line, recipe

The system shall refuse the Pending→Accepted transition unless the order carries planned start date, planned end date, `production_line` and a recipe reference, with the date range consistent (end after start), matching Qcadoo acceptance gating.

- **Priority:** Must
- **Lineage:** Absorb (exact parity) · Qcadoo · `OrderStateValidationService.java:44-47`; date consistency `OrderStateService.java:47-59`
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0002 without `production_line`, When P. Krüger attempts acceptance, Then the gate refuses and names the missing field.
  - **AC-2** Given PO-2026-0002 with start 15.03.2026 and end 14.03.2026, When acceptance is attempted, Then the gate refuses citing the inconsistent date range.
  - **AC-3** Given PO-2026-0001 with dates 10.03.2026–12.03.2026, LINE-1 and BOM-RW-CHM-0003-001 (Accepted), When acceptance is attempted, Then it succeeds.
  - **AC-4** Given the characterisation acceptance-gate contract (URS-W0-012 AC-1), When run against the target, Then it passes (parity).
- **Design conformance:** gate refusal presented per design skill §"Interaction rules — Hard gates look hard": modal (not toast), naming the rule, the record (PO-2026-0002), and what resolves it; refusal logged.
- **Dependencies:** URS-W1-001.

#### URS-W1-006 — Acceptance gate: recipe must be Accepted

The system shall refuse order acceptance when the referenced recipe's `gov_state` is not Accepted, so that only governed recipes reach the shop floor.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo (orders must reference accepted technologies) · CDM-04 semantics ("orders may only reference Accepted recipes — gate in CDM-02 accept"); ADR-006
- **Acceptance criteria:**
  - **AC-1** Given BOM-RW-CHM-0003-001 with `gov_state` = Draft, When P. Krüger attempts to accept PO-2026-0002 referencing it, Then the gate refuses naming the recipe and its `gov_state`.
  - **AC-2** Given the same recipe moved to Accepted (via URS-W1-015), When acceptance is retried, Then it succeeds.
- **Design conformance:** gate refusal modal naming rule/record/resolution (design skill §"Hard gates look hard").
- **Dependencies:** URS-W1-001, URS-W1-014.

#### URS-W1-007 — Completion gate: recorded output > 0

The system shall refuse the In Progress→Completed transition when recorded output is zero or when required execution dates are missing, matching Qcadoo completion gating.

- **Priority:** Must
- **Lineage:** Absorb (exact parity) · Qcadoo · `OrderStateValidationService.java:54-63`
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 In Progress with recorded output 0 kg, When O. Weber attempts completion, Then the gate refuses citing zero recorded output.
  - **AC-2** Given PO-2026-0001 with recorded output 500 kg, When completion is attempted, Then it succeeds.
  - **AC-3** Given the characterisation completion-gate contract (URS-W0-012 AC-2), When run against the target, Then it passes (parity).
- **Design conformance:** gate refusal modal naming rule/record/resolution.
- **Dependencies:** URS-W1-001, URS-W1-004.

#### URS-W1-008 — Material-availability gate on release/start

The system shall check material availability when an order starts (Accepted→In Progress): required component quantities per the recipe must be available (on hand minus reservations) in the source warehouse, refusing the start with a per-component shortfall list otherwise, matching the Qcadoo listener gate.

- **Priority:** Must
- **Lineage:** Absorb (exact parity) · Qcadoo · `OrderStatesListenerServicePFTD.java:580` (material availability checked at order start), `:129,134,633`; dossier §5.4 material-availability row (hard vs soft gate — target adopts the hard gate)
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 requires 500 kg RW-CHM-0001 and RM Lager Nord holds only 400 kg available, When start is attempted, Then the gate refuses listing RW-CHM-0001 with shortfall 100 kg.
  - **AC-2** Given BATCH-A-0001 (500 kg RW-CHM-0001) available in RM Lager Nord, When start is attempted, Then it succeeds.
  - **AC-3** Given a component quantity reserved by another order's draft document (URS-W1-023), When availability is computed, Then the reserved quantity is excluded from availability.
- **Design conformance:** gate refusal modal naming rule/record (the shortfall components)/resolution; logged.
- **Dependencies:** URS-W1-001, URS-W1-021, URS-W1-023.

#### URS-W1-009 — Reservation clearing on Declined/Abandoned

The system shall release all stock reservations held by an order when it transitions to Declined or Abandoned, matching Qcadoo listener behaviour.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `OrderStatesListenerServicePFTD.java:633` (reservations cleared on decline/abandon)
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0002 with an active reservation of 50 kg RW-CHM-0002 (BATCH-A-0002 lineage fixture), When P. Krüger declines the order with a reason, Then the reservation entry is cancelled and the 50 kg returns to available quantity.
- **Dependencies:** URS-W1-001, URS-W1-025.

### 3.3 Anchor hard stops kept/verified (W1-3)

#### URS-W1-010 — Over-production hard stop

The system shall keep the anchor over-production errors: manufacturing or transferring quantity above plan + allowance throws and blocks the posting.

- **Priority:** Must
- **Lineage:** Adopt (exact anchor behaviour) · ERPNext · `services/status.py:29-47` (vs Sales Order), `:208-224` (`StockOverProductionError`); dossier ch. 3.2 §C rules table
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 for 500 kg with 0 % over-production allowance, When O. Weber records a manufacture of 510 kg, Then the posting is refused with the over-production error and no stock ledger entry is written.
- **Dependencies:** URS-W1-004.

#### URS-W1-011 — Stopped-order freeze

The system shall keep the anchor freeze: job-card submission against a stopped Work Order is refused.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext · `job_card.py:904-910`; dossier ch. 3.2 §C rules table
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001's anchor Work Order is stopped, When O. Weber attempts to submit a job card for operation MIX at LINE-1/MIX-01, Then submission is refused citing the stopped order.
- **Dependencies:** URS-W1-026.

#### URS-W1-012 — Closed order is terminal

The system shall keep the anchor rule that a closed Work Order cannot be stopped or re-opened, and shall map anchor Closed consistently with terminal `exec_state`s in the reconciliation hooks.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext · `work_order.py:1131-1132`; dossier ch. 3.2 Work Order lifecycle
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0002's anchor Work Order is Closed, When stop or re-open is attempted, Then it is refused.
- **Dependencies:** URS-W1-004.

#### URS-W1-013 — Expired-batch consumption hard stop

The system shall keep the anchor expired-batch throw: outward stock ledger postings against a batch past its `expiry_date` are refused, and pick lists refuse expired batches — subject to the estate-wide policy decision in URS-W1-030.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext · `stock_ledger_entry.py:287-299` (expired batch throw); `pick_list.py:286-311` (pick list block); dossier §5.4 expired-stock row
- **Acceptance criteria:**
  - **AC-1** Given BATCH-A-0002 (Additiv K7, expiry 30.06.2026) and system date 01.07.2026, When W. Braun attempts an issue of 5 kg from BATCH-A-0002, Then the posting is refused naming the expired batch.
  - **AC-2** Given the same conditions, When a pick list including BATCH-A-0002 is saved, Then the save is refused listing the expired batch.
- **Design conformance:** refusal presented as a hard-gate modal naming rule (expiry policy), record (BATCH-A-0002, expiry 30.06.2026 in DD.MM.YYYY), and resolution (select non-expired stock / QA disposition).
- **Dependencies:** URS-W1-021, URS-W1-030.

### 3.4 Recipe governance workflow (W1-4)

#### URS-W1-014 — `gov_state` workflow on Recipe Governance

The system shall provide the Recipe Governance DocType linking a BOM (and its selected routing) with `gov_state` workflow Draft → Checked → Accepted → Outdated, with Declined reachable from Draft and Checked, matching the Qcadoo technology lifecycle.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `TechnologyState.java:33-66` (5-state lifecycle); ADR-006 / CDM-04; dossier §7 implication 5
- **Acceptance criteria:**
  - **AC-1** Given T. Schmid creates a Recipe Governance record for BOM-RW-CHM-0003-001 with routing RT-COMPOUND-01, Then `gov_state` = Draft.
  - **AC-2** Given the record in Draft, When T. Schmid progresses it, Then Draft→Checked and Checked→Accepted succeed in order; Checked→Draft (rework) also succeeds.
  - **AC-3** Given the record in Accepted, When a transition to Draft or Checked is attempted, Then it is refused (only Accepted→Outdated is legal).
  - **AC-4** Given a record in Checked, When T. Schmid declines it, Then `gov_state` = Declined (terminal).
- **Design conformance:** `gov_state` pill with icon + label + colour; state vocabulary exactly Draft/Checked/Accepted/Outdated/Declined.
- **Dependencies:** URS-W0-006 (W0).

#### URS-W1-015 — Structural validators at Checked→Accepted

The system shall run structural validators when a recipe is accepted — tree/BOM completeness (materials present, output declared as the BOM's item), UoM consistency between BOM lines and item UoM conversions, and routing operation completeness — refusing acceptance with a named validator failure list otherwise, re-implementing the Qcadoo validation battery scoped to the anchor BOM/Routing split.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `TechnologyValidationService.java:91-707` (~20 structural checks incl. tree set, units match, in-components present); CDM-04 semantics; characterisation contract URS-W0-012
- **Acceptance criteria:**
  - **AC-1** Given BOM-RW-CHM-0003-001 with the RW-CHM-0002 line's UoM set to a unit with no conversion for that item, When acceptance is attempted, Then it is refused naming the UoM-consistency validator and the offending line.
  - **AC-2** Given a BOM with no component lines, When acceptance is attempted, Then it is refused naming the completeness validator.
  - **AC-3** Given BOM-RW-CHM-0003-001 corrected (RW-CHM-0001 in kg, RW-CHM-0002 in kg, output 25 kg-batches of RW-CHM-0003, routing RT-COMPOUND-01 with MIX and FILL operations), When acceptance is attempted, Then it succeeds and the validator results are stored on the governance record.
  - **AC-4** Given the characterisation technology-validator contract (URS-W0-012), When run against the target validators, Then the parity assertions pass for the checks in W1 scope (tree completeness, unit match, in-use lock).
- **Dependencies:** URS-W1-014.

#### URS-W1-016 — Accepted recipes are immutable; versioning via Outdated

The system shall make Accepted recipes immutable by policy: changes require a new BOM version whose governance record starts in Draft, and accepting the successor moves the predecessor to Outdated.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `TechnologyState.java` (accepted → outdated, immutable); dossier §5.4 recipe-change row ("change-control strength differs by an order of magnitude"); ADR-006 consequence
- **Acceptance criteria:**
  - **AC-1** Given BOM-RW-CHM-0003-001 Accepted, When T. Schmid attempts to edit its component lines, Then the edit is refused citing recipe immutability.
  - **AC-2** Given a successor BOM version for RW-CHM-0003 whose governance record is accepted, Then the predecessor's `gov_state` automatically becomes Outdated.
- **Dependencies:** URS-W1-014, URS-W1-015.

#### URS-W1-017 — In-use lock

The system shall refuse moving a recipe to Outdated or Declined while it is referenced by an order whose `exec_state` is Accepted, In Progress or Interrupted (in-use lock), matching Qcadoo's not-used-in-active-order check.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `TechnologyValidationService.java:707` (not used in active order); CDM-04 `in_use_lock`
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 In Progress referencing BOM-RW-CHM-0003-001, When T. Schmid attempts to outdate the recipe, Then it is refused naming PO-2026-0001.
  - **AC-2** Given PO-2026-0001 Completed, When the outdate is retried (with an accepted successor), Then it succeeds.
- **Dependencies:** URS-W1-014, URS-W1-001.

### 3.5 Warehouse physical fidelity base (W1-5)

#### URS-W1-018 — Handling Unit DocType

The system shall provide a Handling Unit DocType (id, type, current storage location, contents child table referencing item/batch/quantity) as a referencing layer over the anchor ledger — never a parallel quantity store — so that the warehouse clerk tracks pallets/load units.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `ResourceFields.java:32-90` (palletNumber on lot-level resources); ADR-005 / CDM-03 (Handling Unit as integrity DocType); dossier §7 implication 4
- **Acceptance criteria:**
  - **AC-1** Given warehouse RM Lager Nord, When W. Braun creates handling unit HU-000123 of type "Palette" at storage location NORD-A-01-01 containing 500 kg RW-CHM-0001 (BATCH-A-0001), Then it saves and lists that content row.
  - **AC-2** Given HU-000123, When its content quantities are summed and compared with the anchor ledger quantity for BATCH-A-0001 in RM Lager Nord, Then the ledger is the quantity truth and the HU stores only references (no independent quantity that can diverge without a reconciliation flag).
- **Design conformance:** HU identifiers in mono; scanner path — scanning HU-000123's barcode on any screen expecting identification focuses/loads it (design skill §"Scanner is a first-class input").
- **Dependencies:** URS-W0-003 (W0).

#### URS-W1-019 — Storage Location tree

The system shall provide a Storage Location DocType as a warehouse-scoped tree below the anchor Warehouse (e.g. NORD-A-01-01 under RM Lager Nord), assignable to handling units and batch allocations.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `ResourceFields.java` (storageLocation), storageLocation model `materialFlowResources/model/`; CDM-03
- **Acceptance criteria:**
  - **AC-1** Given RM Lager Nord, When W. Braun creates NORD-A-01-01 under it, Then the location saves scoped to that warehouse and is selectable on HU-000123.
  - **AC-2** Given FG Lager Süd, When NORD-A-01-01 is offered as a location for a handling unit in FG Lager Süd, Then it is not selectable (warehouse-scoped).
- **Dependencies:** URS-W1-018.

#### URS-W1-020 — Per-warehouse disposal algorithm

The system shall support a per-warehouse disposal algorithm (FIFO, LIFO, FEFO, LEFO) governing automatic outbound batch selection, matching Qcadoo's warehouse-level algorithm rather than the anchor's single global setting.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `WarehouseAlgorithm.java:26-27`; `ResourceManagementServiceImpl.java:1015-1027,1207-1220`; dossier ch. 3.2 (`stock_settings.json:363-370` global-only in anchor)
- **Acceptance criteria:**
  - **AC-1** Given RM Lager Nord configured FEFO holding BATCH-A-0001 (expiry 31.12.2026) and BATCH-A-0002 (expiry 30.06.2026), When an automatic issue of 20 kg Additiv-class stock is allocated, Then BATCH-A-0002 is selected first (earliest expiry).
  - **AC-2** Given FG Lager Süd configured FIFO holding BATCH-C-1001 (received first) and BATCH-C-1002, When an automatic issue is allocated, Then BATCH-C-1001 is selected first.
  - **AC-3** Given the characterisation FEFO contract (URS-W0-012 AC-3), When run against the target allocation, Then the parity assertions pass.
- **Dependencies:** URS-W1-021.

#### URS-W1-021 — Batch-aware stock movements on the anchor ledger

The system shall book all W1 stock movements as anchor Stock Entries with batch allocations (Serial and Batch Bundle), with Qcadoo document-type semantics mapped to Stock Entry purposes (Receipt→Material Receipt, Release→Material Issue, Transfer→Material Transfer), so that movement history lives in one immutable ledger.

- **Priority:** Must
- **Lineage:** Adopt (anchor) + Absorb (type mapping) · ERPNext ledger, Qcadoo document taxonomy · ADR-007 / CDM-05; `DocumentType.java:31-35`; dossier §5.2 stock-movement row
- **Acceptance criteria:**
  - **AC-1** Given fixture stock, When W. Braun books a receipt of 500 kg RW-CHM-0001 as BATCH-A-0001 into RM Lager Nord at NORD-A-01-01 on HU-000123, Then a Material Receipt Stock Entry posts with a batch allocation and ledger quantity 500 kg.
  - **AC-2** Given the receipt, When an issue of 100 kg BATCH-A-0001 is booked, Then a Material Issue posts and the remaining ledger quantity is 400 kg.
- **Dependencies:** URS-W1-018, URS-W1-019.

#### URS-W1-022 — Legacy bridge affordance on renamed fields

The system shall offer the legacy field name on hover/long-press for fields renamed from legacy vocabulary (e.g. "was: Technology → now: Recipe", "was: Resource → now: Batch quantity at location"), removable by feature flag after cutover.

- **Priority:** Should
- **Lineage:** Design conformance · design skill §"Interaction rules — Legacy bridge affordance" · legacy vocabulary from dossier ch. 3.1 §B.1
- **Acceptance criteria:**
  - **AC-1** Given the recipe field on a production order, When P. Krüger hovers it, Then the affordance shows "was: Technology".
  - **AC-2** Given the post-cutover feature flag is off, When the same hover occurs, Then no legacy name is shown.
- **Dependencies:** URS-W1-001, URS-W1-014.

### 3.6 Reservations (W1-6)

#### URS-W1-023 — Draft makes reservation

The system shall create Stock Reservation Entries automatically when a draft outbound stock document is saved ("draft makes reservation"), flagged `draft_reservation`, reducing available (not on-hand) quantity, matching Qcadoo draft-document reservation semantics on the anchor SRE.

- **Priority:** Must
- **Lineage:** Absorb + Adopt · Qcadoo `ReservationsService.java:81-247` reconciled with ERPNext `stock_reservation_entry.py:530-553` · ADR-008 / CDM-06; dossier §5.2 reservation row
- **Acceptance criteria:**
  - **AC-1** Given 500 kg BATCH-A-0001 available in RM Lager Nord, When W. Braun saves a draft issue document for 200 kg RW-CHM-0001, Then an SRE flagged `draft_reservation` exists for 200 kg and available quantity shows 300 kg while on-hand remains 500 kg.
- **Dependencies:** URS-W1-021.

#### URS-W1-024 — Draft deletion/rejection releases reservation

The system shall cancel the linked `draft_reservation` SREs when the draft document is deleted or rejected, restoring available quantity.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo · `ReservationsService.java:81-247` (reservations deleted with draft positions); ADR-008
- **Acceptance criteria:**
  - **AC-1** Given the 200 kg draft reservation from URS-W1-023 AC-1, When the draft document is deleted, Then the SRE is cancelled and available quantity returns to 500 kg.
- **Dependencies:** URS-W1-023.

#### URS-W1-025 — Order-level reservations on SRE

The system shall support order-level stock reservations as anchor SREs against the Work Order (auto-reserve on acceptance where configured), so that order and document reservations share one mechanism.

- **Priority:** Should
- **Lineage:** Adopt · ERPNext · `stock_reservation_entry.py:530-553`; `work_order/services/reservation.py`; ADR-008 (order-level reservations = SREs against Work Order, anchor-native)
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 accepted with auto-reserve enabled, When acceptance completes, Then SREs exist reserving 500 kg RW-CHM-0001-class components for the order, visible from the order.
- **Dependencies:** URS-W1-001, URS-W1-023.

### 3.7 Shop-floor operator journey (W1-7)

#### URS-W1-026 — Job-card execution with time logs

The system shall provide the shop-floor operator journey on anchor Job Cards: per-operation job cards spawned from the order, time-log start/stop, and completed-quantity recording feeding the completion gate.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext · `job_card.py:1280-1397` (status, time logs); dossier §6.2 shop-floor execution recording row; §5.3 execute-and-record journey
- **Acceptance criteria:**
  - **AC-1** Given PO-2026-0001 In Progress, When O. Weber opens the shop-floor view, Then job cards for operations MIX (LINE-1/MIX-01) and FILL (LINE-1/FILL-01) are listed against the order.
  - **AC-2** Given the MIX job card, When O. Weber starts and later stops work, Then a time log with start/end timestamps and computed duration is stored.
  - **AC-3** Given the FILL job card, When O. Weber records completed quantity 500 kg and submits, Then submission succeeds and the order's recorded output reflects 500 kg.
- **Design conformance:** Terminal Card pattern (design skill §"Layout patterns" 2): one task at a time, giant primary action, current order/operation in header; Terminal mode 16–18px base, ≥48px touch targets; complete keyboard path (Enter confirms, Esc cancels, arrows move).
- **Dependencies:** URS-W1-001, URS-W1-004.

#### URS-W1-027 — Pause/resume on job cards

The system shall support pause (On Hold) and resume on job cards with time logs split accordingly, matching the anchor pause/resume behaviour.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext · `job_card.py:1371-1397` (pause_job/resume_job); dossier ch. 3.2 Job Card lifecycle
- **Acceptance criteria:**
  - **AC-1** Given O. Weber working the MIX job card, When he pauses, Then the job card is On Hold and the open time log is closed; When he resumes, Then a new time log opens and the card returns to Work In Progress.
  - **AC-2** Given an On Hold job card, When submission is attempted, Then it is refused (anchor completeness rule `job_card.py:912-959`).
- **Dependencies:** URS-W1-026.

#### URS-W1-028 — Scanner-first identification on shop-floor screens

The system shall accept barcode scanner input on every shop-floor screen expecting order, material or batch identification via an always-focused scan field, with full-row visual and audible confirmation on successful scan.

- **Priority:** Must
- **Lineage:** Design conformance · design skill §"Interaction rules — Scanner is a first-class input"; Terminal Card pattern · UI-bearing part of W1-7
- **Acceptance criteria:**
  - **AC-1** Given O. Weber on the terminal job-card screen, When he scans the barcode PO-2026-0001, Then the corresponding job queue loads without any pointer interaction.
  - **AC-2** Given a material-issue step, When he scans BATCH-A-0001, Then the batch row is selected with a visible full-row highlight and an audible confirmation.
  - **AC-3** Given an unknown barcode, When scanned, Then a non-blocking inline error names the unrecognised code and the scan field stays focused.
- **Dependencies:** URS-W1-026.

### 3.8 Role model (W1-8)

#### URS-W1-029 — Workflow-state-level permissions per transition

The system shall gate every `exec_state` and `gov_state` transition by role at the transition level (e.g. only planners accept or decline orders; only operators or planners interrupt; only technologists accept recipes), expressing Qcadoo's per-transition roles in Frappe workflow RBAC — per-DocType rights alone are insufficient.

- **Priority:** Must
- **Lineage:** Absorb (semantics) · Qcadoo 151-role model · dossier ch. 3.1 §B.2; §7 implication 7 (role-model levelling); §5.4 who-may-change-state row
- **Acceptance criteria:**
  - **AC-1** Given O. Weber holds only the shop-floor operator role, When he attempts Pending→Accepted on PO-2026-0002, Then the transition is refused with a permission error and no state change occurs.
  - **AC-2** Given P. Krüger (planner), When she performs Pending→Accepted, Then it succeeds; and given W. Braun (warehouse clerk), When he attempts Checked→Accepted on a recipe, Then it is refused.
  - **AC-3** Given any refused transition, Then the refusal is recorded in the audit log with user, transition attempted and timestamp.
- **Dependencies:** URS-W1-001, URS-W1-014.

### 3.9 Expiry-enforcement policy decision (W1-9)

#### URS-W1-030 — Estate-wide expiry policy: hard stop (deliberate deviation) — **Business sign-off required**

The system shall enforce the estate-wide expiry policy decided for consolidation: **hard stop** on consuming/picking expired batches (anchor behaviour) across all plants, which is a **deliberate deviation** from Plant A's legacy FEFO-advisory behaviour (Qcadoo has no hard stop on issuing expired resources — FEFO ordering only). The decision, its characterisation-test deltas, and the business sign-off reference shall be recorded in the per-gate behaviour record (URS-W1-031). **Business sign-off required** before W1 exit.

- **Priority:** Must
- **Lineage:** Decision · deviation from Qcadoo (`ResourceManagementServiceImpl.java:1015-1027` FEFO-advisory, no hard stop found) toward ERPNext (`stock_ledger_entry.py:287-299` hard stop) · dossier §5.4 expired-stock divergence; §7 implication 6; W1-9 backlog item
- **Acceptance criteria:**
  - **AC-1 (target behaviour)** Given BATCH-A-0002 expired on 30.06.2026 in FEFO warehouse RM Lager Nord and system date 01.07.2026, When automatic allocation runs for Additiv K7, Then BATCH-A-0002 is skipped and the issue is refused if no unexpired stock covers the demand — it is never silently issued.
  - **AC-2 (deviation is explicit)** Given the characterisation harness runs the legacy Plant A expiry contract (expired resource issuable under FEFO-advisory), When compared with the target, Then the delta is reported as an *intentional divergence* linked to the recorded sign-off reference, not as a parity failure.
  - **AC-3 (sign-off gate)** Given the W1 exit checklist, When EXIT-W1 verification runs, Then it fails unless the decision record carries a business sign-off identifier (name/role/date).
- **Design conformance:** expiry refusals presented as hard-gate modals naming rule/record/resolution; expiring batches flagged with the amber signal state (design skill §"Design tokens — Color").
- **Dependencies:** URS-W1-013, URS-W1-020.

### 3.10 Characterisation-vs-behaviour record (W1-10)

#### URS-W1-031 — Per-gate parity/divergence record

The system shall document, for every gate delivered in W1 (acceptance gate, recipe-Accepted gate, completion gate, material-availability gate, transition legality, over-production, stopped freeze, closed terminal, expiry policy, in-use lock), whether the target behaviour is characterisation parity or intentional divergence, each row citing the legacy source path and — for divergences — the sign-off reference; the record is generated from harness results, not hand-maintained.

- **Priority:** Must
- **Lineage:** Wave exit criterion · — · `docs/waves/W1-production-core.md` W1-10; ADR-001 consequence; URS-W0-013 evidence-pack generator
- **Acceptance criteria:**
  - **AC-1** Given the W1 harness run, When the record is generated, Then it contains one row per gate above with verdict Parity or Divergence and the legacy citation (e.g. `OrderStateValidationService.java:44-63`).
  - **AC-2** Given the expiry-policy row, Then its verdict is Divergence and it links the URS-W1-030 sign-off reference; all other W1 rows are Parity unless separately signed off.
  - **AC-3** Given a harness contract failure without a recorded divergence, When the record is generated, Then generation fails, blocking W1 exit.
- **Dependencies:** URS-W1-002, URS-W1-005, URS-W1-007, URS-W1-008, URS-W1-015, URS-W1-030.

## 4. Non-functional requirements (W1-10)

#### URS-W1-032 — Shop-floor interaction latency

The system shall confirm scanner and gated actions from the server within 300 ms (95th percentile) on the shop-floor terminal, with UI feedback within 100 ms for all actions; gated actions are never optimistically confirmed.

- **Priority:** Must
- **Lineage:** Design conformance · design skill §"Interaction rules — No dead air" (under 100 ms feels instant; gated actions always confirm from the server) · applies to URS-W1-026/028 journeys
- **Acceptance criteria:**
  - **AC-1** Given a load test of 100 sequential scans of BATCH-A-0001 on the terminal, Then p95 server-confirmed scan-to-confirmation latency ≤ 300 ms and every scan shows UI feedback < 100 ms.
  - **AC-2** Given a completion action while the server is artificially delayed 2 s, Then the UI shows progress on the control itself and does not display success before server confirmation.

#### URS-W1-033 — Audit and logging of gated actions

The system shall log every gate evaluation that refuses an action (gate name, record, user, timestamp, refusing rule) and every state transition, retrievable per order/recipe for the business viewer, with log entries immutable.

- **Priority:** Must
- **Lineage:** Absorb (audit semantics) · Qcadoo state-change audit `orderStateChange.xml:36-47` extended per design skill §"Hard gates look hard" ("gate refusals are … logged")
- **Acceptance criteria:**
  - **AC-1** Given the refused acceptance in URS-W1-005 AC-1, When B. Vogel opens the order's audit view, Then the refusal appears with gate name, missing field, user and timestamp.
  - **AC-2** Given any audit entry, When modification is attempted via API, Then it is refused.

#### URS-W1-034 — German-first i18n and units on W1 screens

The system shall render all W1 screens (order workflow, recipe governance, warehouse, shop floor) German-first with externalized strings, DD.MM.YYYY dates and kg quantities, including gate-refusal texts.

- **Priority:** Must
- **Lineage:** Design conformance · design skill §"Content and language" · extends URS-W0-016 to W1 scope
- **Acceptance criteria:**
  - **AC-1** Given locale de, When the URS-W1-013 expiry refusal fires, Then the modal shows the expiry as 30.06.2026 and quantities in kg, from externalized strings.
  - **AC-2** Given the W1 string catalogue, When scanned, Then every user-facing W1 string has a German translation entry.

#### URS-W1-035 — Desk/Terminal mode conformance for W1 screens

The system shall render every W1 UI-bearing screen correctly in both Desk mode (13–14px base, 32px rows, full density) and Terminal mode (16–18px base, ≥48px targets, larger status pills, same information — never hidden), with mode auto-selected by station profile and manually switchable in one tap; status is never colour-only.

- **Priority:** Must
- **Lineage:** Design conformance · design skill §"Density modes", §"Component rules — Status pill", §"Definition of done"
- **Acceptance criteria:**
  - **AC-1** Given the job-card screen in Terminal mode, When measured, Then base font ≥16px and all touch targets ≥48px, and the same fields visible in Desk mode are present.
  - **AC-2** Given any `exec_state`/`gov_state` pill, When rendered in grayscale, Then the state remains distinguishable by icon + label (not colour-only).
  - **AC-3** Given any W1 screen, When `?` is pressed, Then the per-screen shortcut sheet opens listing the complete keyboard path.

## 5. Data migration requirements

W1 lands **no migrated data** (W0 migrated master data; open batches/genealogy history land in W2, backfills in W4 — see §1 out-of-scope). W1 fixtures (BATCH-A-0001/0002, PO-2026-0001/0002, HU-000123 etc.) are test data created through the W0 tooling, not migrations. No source→canonical mapping, reconciliation or rollback requirements arise in this wave.

## 6. Wave exit criteria

Restated from `docs/waves/W1-production-core.md` ("planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented") and decomposed:

| ID | Check | Verified by |
|---|---|---|
| EXIT-W1-1 | Planner journey passes acceptance: create → accept (all gates) → release/start with material availability → monitor, on fixture PO-2026-0001 | URS-W1-001…009, URS-W1-025 |
| EXIT-W1-2 | Operator journey passes acceptance: job cards, time logs, pause/resume, scanner path, record output → order completion, on PO-2026-0001 | URS-W1-026…028, URS-W1-007 |
| EXIT-W1-3 | Recipe governance live: Draft→Checked→Accepted with validators, immutability, in-use lock; orders gate on Accepted recipes | URS-W1-014…017, URS-W1-006 |
| EXIT-W1-4 | Warehouse fidelity base live: HU + storage locations + per-warehouse disposal algorithms + draft reservations, ledger remains single quantity truth | URS-W1-018…025 |
| EXIT-W1-5 | Behaviour choices vs characterisation tests documented per gate, generated from harness results; expiry-policy divergence carries business sign-off | URS-W1-030, URS-W1-031 |
| EXIT-W1-6 | Role model enforces per-transition permissions; all gated actions audited; design conformance (Desk/Terminal, pills, i18n, latency) verified | URS-W1-029, URS-W1-032…035 |

## 7. Untraceable / deferred

- None untraceable. All requirements trace to W1 backlog items, ADRs/CDM, dossier evidence or the design skill.
- **Open-question dependency (flagged, not invented):** dossier §8.2 Q1 — Plant C's operated settings (inspection severity, negative stock, capacity planning) materially change gating behaviour. URS-W1-010/013 assert shipped anchor behaviour; the operated-settings confirmation must be attached to the W1 exit evidence. No requirement is written for settings we cannot yet trace.
- Deferred by design: blocked/quarantined batch exclusion from picking (needs `qa_state`, W2-3); QI gates on job cards (W2-4); quarantine storage locations (W2-8).
- Sizing note: 35 requirements — within the 25–40 guide; the count reflects one requirement per independently testable gate rather than padding.
