# URS W2 — Traceability & Quality

**Programme:** Rheinwerk Chemie GmbH — MES consolidation
**Wave:** W2 (Traceability & Quality) — backlog `docs/waves/W2-traceability-quality.md` (W2-1…W2-10)
**Document type:** User Requirements Specification
**Companion document:** `docs/test/TST-W2-traceability-quality.md`

---

## 1. Purpose & scope

Wave W2 delivers the chemicals-critical traceability and quality capability of the consolidated MES: the genealogy object model as system-of-record (Absorb Qcadoo), the unified canonical Batch carrying identity + qa_state + expiry + genealogy links (ADR-003/CDM-01), batch blocking/quarantine with propagation through genealogy trees and exclusion from picking, adoption of the ERPNext Quality Inspection engine wired to the W1 execution state machine (ADR-009/CDM-07), and three white-space rebuilds: Certificates of Analysis, ISA-88 batch recipes with scaling, and hazmat/regulatory master data (dossier §6.3). It also completes warehouse physical fidelity (quarantine locations, pallet balances, stocktaking/repacking) and records the e-signature decision (W2-10). The wave closes when full multi-level trace is demonstrable, CoA is generated from inspection results, and recipe scaling is functional (wave exit, `docs/plan/consolidation-project-plan.md` M2).

**Out of scope for W2** (visible scope boundary, pulled from later waves):

- MRP / production planning journeys and finite-capacity scheduling (W3-1, W3-2)
- Group-ERP interface, costing/valuation GL boundary (W3-3, W3-4)
- SCADA/OPC-UA adapter — tracking events from process control (W3-5)
- Hazmat *shipping/ADR boundary and label data* — W2 lands master data only; boundary completion is W3-6
- Per-plant cutover, Plant A/B genealogy and stock backfill at production scale (W4-2, W4-3, W4-4) — W2 lands the migration *mechanism* and pilot reconciliation only
- E-signature *implementation* if the W2-10 decision selects it — W2 delivers the decision record and the enforcement point design, not a Part-11 subsystem

## 2. Personas in scope

From the dossier role model (dossier ch. 3.1 §B.2 role groups; ch. 3.2 §B personas):

| Persona | W2 relevance | Evidence |
|---|---|---|
| Quality inspector ("Q. Fischer") | Quality Inspections, batch disposition (Release/Block), CoA issue | dossier ch. 3.2 §B — `Quality Manager` role on Quality Inspection (`quality_inspection.json`); ch. 3.1 §B.2 quality/genealogy officer (`ROLE_ADVANCED_GENEALOGY`, `ROLE_BATCHES`) |
| Warehouse clerk ("W. Braun") | Quarantine locations, picking exclusion, stocktaking/repacking, pallet balances | dossier ch. 3.1 §B.2 warehouse operator (`ROLE_DOCUMENTS_STATES_ACCEPT`, `ROLE_DOCUMENT_POSITIONS`) |
| Shop-floor operator ("O. Weber") | Genealogy capture at consumption/production, gate refusals at the terminal | dossier ch. 3.1 §B.2; ch. 3.2 `Manufacturing User` |
| Technologist ("T. Schmid") | ISA-88 recipe authoring and scaling, QI templates, hazmat master data | dossier ch. 3.1 §B.2 master-data manager; ch. 3.2 `Manufacturing Manager`, `Item Manager` |
| Business viewer ("B. Vogel") | Trace Ribbon drill-down, recall evidence, CoA retrieval | design skill "The three audiences" — business/management |

Planner ("P. Krüger") is **out of scope** for W2 (planning journeys are W3); the planner appears only as fixture context on production orders created in W1 scope.

## 3. Requirements

Requirement IDs: `URS-W2-NNN`. Priorities: MoSCoW. Each requirement carries a one-line lineage block: disposition · golden source · evidence. State vocabulary is fixed: `qa_state` ∈ {Quarantined, Released, Blocked}; `exec_state` ∈ {Pending, Accepted, In Progress, Completed, Interrupted, Abandoned, Declined}; `gov_state` ∈ {Draft, Checked, Accepted, Outdated, Declined}. "Status" is never used unqualified.

### 3.1 Genealogy object model (W2-1)

#### URS-W2-001 — Genealogy links as system-of-record

The system shall record, for every production order that consumes or produces batch-managed material, genealogy links (direction consumed/produced, batch, production order, quantity) on the canonical Batch, so that the quality inspector can reconstruct lineage without deriving it from stock ledger joins.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo Advanced Genealogy · `TrackingRecordFields.java:31-49` (producedBatch ↔ usedBatchesSimple); ADR-003/CDM-01 `genealogy_links` child table
- **Acceptance criteria:**
  - AC-1: Given PO-2026-0001 (500 kg Rheinol 40 Compound on LINE-1) in exec_state In Progress consuming BATCH-A-0001 (Rheinol 40 Basisharz, 480 kg) and BATCH-A-0002 (Additiv K7, 20 kg), When O. Weber records output producing BATCH-C-1001, Then BATCH-C-1001 carries two `consumed` genealogy links (BATCH-A-0001 qty 480 kg; BATCH-A-0002 qty 20 kg) and one `produced` link referencing PO-2026-0001.
  - AC-2: Given the links in AC-1 exist, When any of the linked stock entries is cancelled and reposted, Then the genealogy links remain the system-of-record and are corrected by the same transaction — a reconciliation query between genealogy links and SLE-derived trace returns zero divergent rows.
  - AC-3: Given a production order consuming a non-batch-managed material (e.g. process water), When output is recorded, Then no genealogy link is created for that material and the produced batch's genealogy is still considered complete (no `genealogy_incomplete` flag).
- **Dependencies:** W1-1 state machine (URS-W1-xxx, exec_state transitions); W0 canonical Batch scaffold.

#### URS-W2-002 — Forward and backward tree browsing

The system shall let the quality inspector browse the genealogy of any batch in both directions — backward ("produced from") to supplier batches and forward ("used to produce") to finished-goods batches — across an arbitrary number of levels.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo Advanced Genealogy · `AdvancedGenealogyTreeViewListeners.java:71-73` (producedFrom / usedToProduce directions)
- **Acceptance criteria:**
  - AC-1: Given BATCH-C-1001 produced from BATCH-A-0001 and BATCH-A-0002 (URS-W2-001 AC-1), When Q. Fischer opens the backward trace of BATCH-C-1001, Then both raw batches appear at level 1 with their consumed quantities (480 kg / 20 kg).
  - AC-2: Given BATCH-A-0002 was consumed into BATCH-C-1001 and BATCH-C-1002, When Q. Fischer opens the forward trace of BATCH-A-0002, Then both FG batches appear with the production order that links them (PO-2026-0001, PO-2026-0002).
  - AC-3: Given a three-level chain (supplier batch → intermediate batch → BATCH-C-1001), When the backward trace is expanded to all levels, Then the supplier batch appears at level 2 and the trace terminates with no cycle and no duplicate visit of a node.
- **Dependencies:** URS-W2-001.

#### URS-W2-003 — Trace Ribbon genealogy UI

The system shall render batch genealogy as the Trace Ribbon: a horizontal flowing ribbon with supplier batches on the left, the batch in focus centred, and downstream products on the right; blocked branches rendered in signal-red with a hard visual break; interactive (expand levels, jump to any batch), printable, and identical in the CoA and recall views.

- **Priority:** Must
- **Lineage:** Absorb + extend · Qcadoo tree semantics rendered per design skill · `AdvancedGenealogyTreeViewListeners.java:71-73`; design skill "Layout patterns" #4 (The Trace Ribbon — signature element)
- **Acceptance criteria:**
  - AC-1: Given BATCH-C-1001 with the genealogy of URS-W2-001 AC-1, When B. Vogel opens the Trace Ribbon for BATCH-C-1001, Then BATCH-A-0001 and BATCH-A-0002 render left of centre, BATCH-C-1001 centred, and any downstream consumption right of centre.
  - AC-2: Given BATCH-A-0002 is Blocked, When the ribbon for BATCH-C-1001 renders, Then the BATCH-A-0002 branch renders in `--rw-signal-red` with a hard visual break and its status pill shows icon + label "Blocked" + colour.
  - AC-3: Given the ribbon is open, When Q. Fischer activates the batch chip of BATCH-A-0001 (mouse or Enter on the focused chip), Then the ribbon re-centres on BATCH-A-0001 without losing the expansion state of already-expanded levels.
  - AC-4: Given the ribbon is open, When the print action is invoked, Then a print rendering identical in structure to the on-screen ribbon is produced (status conveyed by icon + label, not colour alone).
- **Design conformance:** design skill pattern 4 (Trace Ribbon); status pill = icon + label + colour (Component rules); batch chip = mono ID + status dot + one-click to Trace Ribbon; keyboard path per Interaction rules (arrows move focus, Enter opens, Esc closes); renders in Desk and Terminal modes with identical information.
- **Dependencies:** URS-W2-002, URS-W2-009 (blocked rendering).

#### URS-W2-004 — Genealogy completeness marking

The system shall mark any batch whose lineage is not fully recorded (migrated Qcadoo resource-string batches without matched genealogy Batch; OFBiz history behind the trace boundary) with the `genealogy_incomplete` flag, visible wherever the batch is traced.

- **Priority:** Must
- **Lineage:** Absorb + migration rule · ADR-003 consequences (`genealogy_incomplete`, trace-boundary) · dossier §7 implication 9; §8.2 Q2/Q3
- **Acceptance criteria:**
  - AC-1: Given a migrated batch created from an unmatched Qcadoo `Resource.batch` string, When it is saved by the migration, Then `genealogy_incomplete = true` and the Trace Ribbon renders the flag as an amber advisory pill (icon + label "Trace incomplete") on that node.
  - AC-2: Given a batch with `genealogy_incomplete = true`, When it appears in a backward trace, Then the trace does not silently terminate: the incomplete node is shown with the advisory and the recorded trace-boundary date where applicable (OFBiz history).
- **Dependencies:** URS-W2-030 (migration), URS-W2-001.

### 3.2 Unified batch object (W2-2)

#### URS-W2-005 — Canonical Batch: identity + qa_state + expiry + genealogy

The system shall provide one canonical Batch object per lot carrying identity (`batch_id`, item, qty_original/uom, supplier_batch_no, legacy_refs), qa_state (Quarantined/Released/Blocked), expiry (manufacturing_date, expiry_date), and genealogy links — extending the anchor Batch DocType, never forking it.

- **Priority:** Must
- **Lineage:** Absorb + extend · ADR-003/CDM-01 · dossier §7 implication 2; ch. 3.1 §B.4 (dual model); ch. 3.2 `batch.py:97-115` (stateless anchor Batch)
- **Acceptance criteria:**
  - AC-1: Given the technologist creates BATCH-A-0001 for RW-CHM-0001 "Rheinol 40 Basisharz" with 500 kg and expiry 31.12.2026, When the batch is saved, Then it carries `batch_id` BATCH-A-0001, item RW-CHM-0001, qty_original 500 kg, expiry_date 31.12.2026 and qa_state Quarantined (default at creation).
  - AC-2: Given an item flagged shelf-life-managed, When a batch is created without expiry_date, Then save is refused naming the missing field (parity with anchor `batch.py:194-220` mandatory-expiry throw).
  - AC-3: Given BATCH-A-0001 exists, When its record is inspected via the API, Then the anchor Batch DocType is unmodified (extensions live in custom fields / linked DocTypes) — verified by schema diff against the anchor.
- **Dependencies:** W0 canonical-entity scaffold; ADR-003 sign-off (**Business sign-off required** — ADR-003 status is Proposed).

#### URS-W2-006 — qa_state workflow

The system shall govern qa_state by workflow: batches are created Quarantined (or Released where QC-exempt), move Quarantined → Released only by Quality Inspection acceptance, and move Blocked ⇄ Released only by a quality-inspector decision with a mandatory reason.

- **Priority:** Must
- **Lineage:** Absorb + extend · Qcadoo `BatchState.java:31-44` (TRACKED⇄BLOCKED, reversible) extended with Quarantined per ADR-003 · CDM-01 lifecycle
- **Behaviour-parity note:** legacy Qcadoo has only TRACKED⇄BLOCKED; the Quarantined entry state is a **deliberate deviation** beyond all three sources (ADR-003 "deliberately designed beyond all three"). **Business sign-off required** for the Quarantined-by-default policy (QC-exempt item list).
- **Acceptance criteria:**
  - AC-1: Given BATCH-C-1001 is created by production receipt, When creation completes, Then qa_state = Quarantined and its stock is excluded from picking (URS-W2-010).
  - AC-2: Given BATCH-C-1001 is Quarantined and its Quality Inspection (QIT-COMPOUND) is accepted, When the inspection is submitted as Accepted, Then qa_state transitions to Released automatically and the transition is audited (user, timestamp, triggering inspection).
  - AC-3: Given BATCH-A-0002 is Released, When Q. Fischer blocks it without entering a reason, Then the transition is refused; When a reason ("supplier recall K7/2026-06") is entered, Then qa_state = Blocked and reason, user and timestamp are recorded.
  - AC-4: Given BATCH-A-0002 is Blocked, When O. Weber (shop-floor operator role) attempts to unblock it, Then the transition is refused as a permission gate — only the quality-inspector role may transition qa_state.
  - AC-5: Given any batch, When a transition not in the workflow (e.g. Quarantined → Blocked skipping inspection disposition, or Released → Quarantined) is attempted via UI or API, Then it is rejected naming the allowed transitions.
- **Dependencies:** URS-W2-013 (QI wiring); W1-8 role model (URS-W1-xxx).

#### URS-W2-007 — Legacy reference preservation

The system shall preserve every legacy identifier of a batch (Qcadoo genealogy batch number, Qcadoo resource batch string, ERPNext batch_no, OFBiz lotId) in the `legacy_refs` child table, and offer the legacy field name on hover per the legacy-bridge affordance.

- **Priority:** Must
- **Lineage:** Absorb (migration) · ADR-003/CDM-01 `legacy_refs` · dossier §5.2 batch/lot row (dual model, four meanings)
- **Acceptance criteria:**
  - AC-1: Given a migrated batch merged from Qcadoo genealogy batch "GB-4711" and resource batch string "RB-4711", When the batch is opened, Then `legacy_refs` lists both (system=Qcadoo, ref values preserved verbatim).
  - AC-2: Given a field mapped from a legacy system (e.g. expiry_date from `Resource.expirationDate`), When the user hovers/long-presses the field label, Then the legacy origin is shown ("was: Resource.expirationDate → now: expiry_date"), removable by feature flag after cutover.
- **Design conformance:** design skill Interaction rules — legacy bridge affordance.
- **Dependencies:** URS-W2-030 (migration).

#### URS-W2-008 — Expiry drives FEFO and the hard stop

The system shall carry expiry on the canonical Batch such that FEFO picking (RM Lager Nord) orders by expiry_date and consumption of an expired batch is refused per the W1 expiry policy decision.

- **Priority:** Must
- **Lineage:** Adopt ERPNext hard stop + Absorb Qcadoo FEFO · `stock_ledger_entry.py:287-299` (expired-batch throw); `WarehouseAlgorithm.java:26-27` (FEFO) · policy per W1-9 decision (**Business sign-off required** — W1-9 records the estate-wide policy; W2 inherits it)
- **Acceptance criteria:**
  - AC-1: Given RM Lager Nord (FEFO) holds BATCH-A-0001 (expiry 31.12.2026) and a second Basisharz batch expiring 30.09.2026, When W. Braun picks 100 kg of RW-CHM-0001, Then the batch expiring 30.09.2026 is proposed first.
  - AC-2: Given BATCH-A-0002 has expiry_date 30.06.2026 and today is 01.07.2026, When an issue against BATCH-A-0002 is submitted, Then the posting is refused naming the batch and its expiry date (per the signed-off W1-9 policy; if W1-9 selected FEFO-advisory for Plant A journeys, this AC executes in the hard-stop configuration and the advisory configuration is exercised in parity tests).
- **Dependencies:** W1-9 decision, W1-5 warehouse fidelity base (URS-W1-xxx).

### 3.3 Batch blocking / quarantine with propagation (W2-3)

#### URS-W2-009 — Blocking propagates advisories through genealogy

The system shall, when a batch is Blocked, propagate an advisory flag to all downstream batches in its forward genealogy (all levels), and clear the advisory when the batch is unblocked and no other blocked ancestor remains.

- **Priority:** Must
- **Lineage:** Absorb + extend · Qcadoo blocking (`BatchState.java:31-44`) extended with propagation per dossier §7 implication 3 ("blocking must propagate through genealogy trees — none does the former automatically") · ADR-003 consequences
- **Behaviour-parity note:** propagation is a **deliberate deviation** beyond legacy behaviour (no legacy system propagates). **Business sign-off required** for advisory semantics (downstream batches flagged, not auto-Blocked).
- **Acceptance criteria:**
  - AC-1: Given BATCH-A-0002 was consumed into BATCH-C-1001 and BATCH-C-1002, When Q. Fischer blocks BATCH-A-0002, Then both FG batches receive a blocked-ancestor advisory naming BATCH-A-0002 within the same transaction.
  - AC-2: Given the advisory of AC-1, When Q. Fischer unblocks BATCH-A-0002 (reason recorded) and no other ancestor of BATCH-C-1001/1002 is Blocked, Then the advisories are cleared.
  - AC-3: Given BATCH-C-1001 carries a blocked-ancestor advisory, When it renders anywhere (queue, ribbon, batch chip), Then the advisory shows as an amber pill (icon + label "Blocked ancestor: BATCH-A-0002") — the batch's own qa_state is unchanged.
- **Design conformance:** status pill icon + label + colour; ribbon blocked-branch rendering per URS-W2-003 AC-2.
- **Dependencies:** URS-W2-001, URS-W2-006.

#### URS-W2-010 — Blocked and Quarantined stock excluded from picking

The system shall exclude all stock of Blocked and Quarantined batches from picking proposals, reservations and issue documents, in every warehouse and for every disposal algorithm.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo `ResourceCriteriaModifiers.java:59,70` (QC-blocked resources excluded from lookups) + extend to Quarantined per ADR-003 lifecycle
- **Acceptance criteria:**
  - AC-1: Given BATCH-A-0002 (50 kg Additiv K7 in RM Lager Nord) is Blocked, When W. Braun creates a pick for 5 kg of RW-CHM-0002, Then BATCH-A-0002 is absent from the proposal; if it is the only stock, the pick fails naming the blocked batch as the reason.
  - AC-2: Given BATCH-C-1001 is Quarantined in FG Lager Süd, When a delivery reservation for RW-CHM-0003 is attempted, Then BATCH-C-1001 quantity is not reservable and the availability figure excludes it.
  - AC-3: Given an operator scans HU-000123 containing Blocked stock at a terminal issue screen, When the scan is confirmed, Then a gate-refusal modal names the rule (blocked-batch exclusion), the record (BATCH-A-0002, HU-000123) and the resolution (QA unblock required), and the refusal is logged.
- **Design conformance:** gate refusals are modal, never a toast; name rule/record/resolution (design skill "Hard gates look hard"); scanner path with full-row confirmation.
- **Dependencies:** URS-W2-006; W1-5/W1-6 warehouse + reservation base (URS-W1-xxx).

#### URS-W2-011 — Blocking excludes batches from further genealogy use

The system shall refuse recording consumption of a Blocked batch into any production order, at both the UI gate and the posting hook.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo "batch must be unblocked (TRACKED) before further use" · `BatchState.java:31-44`; `BatchBasicStateListenerService.java` (dossier ch. 3.1 §C.3)
- **Acceptance criteria:**
  - AC-1: Given PO-2026-0002 In Progress and BATCH-A-0002 Blocked, When O. Weber scans BATCH-A-0002 for consumption, Then the terminal refuses with a gate-refusal modal (rule: blocked-batch consumption; record: BATCH-A-0002; resolution: QA unblock) and no genealogy link is written.
  - AC-2: Given the same setup, When consumption is attempted directly via API (bypassing UI), Then the server hook refuses the posting with the same rule identifier — server-side enforcement is authoritative.
- **Design conformance:** gate refusal modal naming rule/record/resolution; gated actions confirm from the server (no optimistic UI).
- **Dependencies:** URS-W2-006, URS-W2-001.

#### URS-W2-012 — Quarantine storage locations

The system shall support flagging Storage Locations as quarantine locations; stock of Quarantined batches put away in a quarantine-flagged location, and movements out of quarantine locations, require the quality-inspector or warehouse-clerk role per transition.

- **Priority:** Should
- **Lineage:** Absorb · Qcadoo storage-location model · `storageLocation.xml:37-54` (location flags) + ADR-005/CDM-03 Storage Location extension; W2-8 backlog item
- **Acceptance criteria:**
  - AC-1: Given NORD-A-01-01 is flagged as a quarantine location, When BATCH-C-1001 (Quarantined) is received, Then the putaway proposal targets NORD-A-01-01.
  - AC-2: Given Quarantined stock in NORD-A-01-01, When O. Weber (operator role) attempts a transfer out, Then the movement is refused as a role gate; When W. Braun performs it after the batch is Released, Then it posts.
- **Dependencies:** URS-W2-006; W1-5 storage-location DocType (URS-W1-xxx).

### 3.4 Quality Inspection engine (W2-4)

#### URS-W2-013 — Adopt typed, template-driven Quality Inspections

The system shall provide Quality Inspections of types Incoming, Outgoing and In Process with parametric readings (numeric min/max, value match, formula acceptance) instantiated from per-item templates, used as-is from the anchor.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext QI engine · `quality_inspection.py:265-336` (auto accept/reject from readings, min/max, `safe_eval` formula); `quality_inspection.json:74,237` (types, Accepted/Rejected/Cancelled)
- **Acceptance criteria:**
  - AC-1: Given template QIT-COMPOUND (viscosity 1200–1400 mPa·s; density 1.02–1.06 g/cm³; moisture ≤ 0.5 %) assigned to RW-CHM-0003, When Q. Fischer creates an In Process inspection for BATCH-C-1001, Then all three parameters are instantiated with their limits.
  - AC-2: Given readings viscosity 1290 mPa·s, density 1.04 g/cm³, moisture 0.3 %, When the inspection is evaluated, Then every reading passes and the inspection result is Accepted automatically.
  - AC-3: Given a reading viscosity 1450 mPa·s, When the inspection is evaluated, Then the inspection result is Rejected and the failing parameter and limit are identified on the reading row.
- **Dependencies:** W0 anchor platform; template master data (technologist).

#### URS-W2-014 — QI gates wired to the W1 state machine

The system shall wire Quality Inspection gates to the execution state machine: a production order whose produced batch requires inspection cannot reach exec_state Completed while a required inspection is missing, unsubmitted or Rejected; inspection severity is fixed to Stop (refusal), not warn.

- **Priority:** Must
- **Lineage:** Adopt + wire · ERPNext QI gating (`quality_inspection_service.py:21-127`; `job_card.py:843-889`) wired to Absorb-Qcadoo exec_state (W1-1) · dossier §8.2 Q1 (severity setting) — **Business sign-off required**: severity fixed to Stop estate-wide deviates from Plant C's configurable behaviour
- **Acceptance criteria:**
  - AC-1: Given PO-2026-0001 In Progress with output BATCH-C-1001 and no submitted inspection, When O. Weber attempts to complete the order, Then a gate-refusal modal names the rule (QI-required gate), the record (PO-2026-0001, BATCH-C-1001, QIT-COMPOUND) and the resolution (submit an Accepted inspection), and exec_state remains In Progress.
  - AC-2: Given the inspection for BATCH-C-1001 is Rejected, When completion is attempted, Then the refusal names the Rejected inspection; the permitted paths are QA disposition of the batch (Blocked or rework) — completion stays gated.
  - AC-3: Given the inspection is Accepted, When completion is attempted, Then exec_state transitions to Completed and BATCH-C-1001 qa_state is Released (URS-W2-006 AC-2).
- **Design conformance:** gate refusal modal naming rule/record/resolution; server-confirmed gating.
- **Dependencies:** W1-1/W1-2 state machine + gating hooks (URS-W1-xxx); URS-W2-006, URS-W2-013.

#### URS-W2-015 — Inspection queue for the quality inspector

The system shall provide the quality inspector a Work Queue → Detail screen of due inspections (filterable by type, item, batch, production order), with reading entry optimised for keyboard and units suffixed inside inputs.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext QI engine, presented per design skill · `quality_inspection.py`; design skill Layout pattern 1 (Work Queue → Detail)
- **Acceptance criteria:**
  - AC-1: Given inspections due for BATCH-C-1001 and BATCH-C-1002, When Q. Fischer opens the inspection queue, Then both appear with batch chip, item, type and due indication; arrow keys move the selection and Enter opens the detail.
  - AC-2: Given the detail for BATCH-C-1001 open, When Q. Fischer enters readings, Then units (mPa·s, g/cm³, %) render suffixed inside the inputs, validation is inline on blur, and no entered value is lost on a failed submit.
  - AC-3: Given an empty queue, When the queue renders, Then the empty state directs ("No inspections due — next scheduled …"), never decorates.
- **Design conformance:** Work Queue → Detail; keyboard-first parity (`?` shortcut sheet); forms label-above-field, units suffixed, inline validation; Desk and Terminal modes render the same information.
- **Dependencies:** URS-W2-013.

#### URS-W2-016 — Rejection routes to QA disposition

The system shall route a Rejected inspection to an explicit QA disposition on the batch — Blocked (with reason) or rework reference — so no Rejected result leaves a batch in an undispositioned state.

- **Priority:** Must
- **Lineage:** Adopt + extend · ADR-009/CDM-07 ("rejection routes to QA disposition (Blocked or rework)") · `quality_inspection.py:265-281`
- **Acceptance criteria:**
  - AC-1: Given the inspection for BATCH-C-1002 is Rejected, When Q. Fischer opens the disposition action, Then the choices are Block batch or Assign rework (reference to a rework production order), each requiring a reason.
  - AC-2: Given no disposition has been recorded, When a nightly integrity check runs, Then BATCH-C-1002 is listed as "Rejected without disposition" in the quality inspector's queue.
- **Dependencies:** URS-W2-006, URS-W2-013.

### 3.5 Certificates of Analysis (W2-5)

#### URS-W2-017 — CoA generated from accepted inspections

The system shall generate a Certificate of Analysis per batch from its accepted inspection results: a CoA Certificate record (link batch; readings snapshot; approved signatory; issue date) with a PDF artefact.

- **Priority:** Must
- **Lineage:** Rebuild (white space — absent in all three, dossier §6.3) · ADR-009/CDM-07 CoA Certificate spec
- **Acceptance criteria:**
  - AC-1: Given BATCH-C-1001 is Released with an Accepted QIT-COMPOUND inspection (viscosity 1290 mPa·s, density 1.04 g/cm³, moisture 0.3 %), When Q. Fischer issues the CoA, Then a CoA Certificate is created snapshotting the three readings with limits, batch identity BATCH-C-1001, item RW-CHM-0003, signatory Q. Fischer and issue date, and a PDF artefact is attached.
  - AC-2: Given a batch with no Accepted inspection (Quarantined or Rejected), When CoA issue is attempted, Then it is refused naming the missing/failed inspection.
  - AC-3: Given the CoA of AC-1 is issued and the underlying inspection is later cancelled/amended, When the CoA is viewed, Then the snapshot is unchanged (immutability) and the CoA is marked as superseded only by issuing a new version.
- **Dependencies:** URS-W2-013, URS-W2-006.

#### URS-W2-018 — CoA embeds the Trace Ribbon

The system shall render the batch's Trace Ribbon (identical to the browsing view) inside the CoA view and its print rendering.

- **Priority:** Should
- **Lineage:** Rebuild · design skill pattern 4 ("identical in the CoA and recall views")
- **Acceptance criteria:**
  - AC-1: Given the CoA for BATCH-C-1001, When it is viewed, Then the embedded ribbon shows the same nodes and states as the standalone ribbon for BATCH-C-1001 at the same instant.
- **Design conformance:** Trace Ribbon identical in CoA and recall views; print-safe (icon + label, not colour-only).
- **Dependencies:** URS-W2-003, URS-W2-017.

#### URS-W2-019 — CoA retrieval for business viewers

The system shall let the business viewer retrieve issued CoAs by batch, item or customer-facing identifier without training, via the Command Dashboard drill-down.

- **Priority:** Should
- **Lineage:** Rebuild · design skill Layout pattern 3 (Command Dashboard — lens on the same data)
- **Acceptance criteria:**
  - AC-1: Given issued CoAs exist, When B. Vogel searches "BATCH-C-1001" from the dashboard, Then the CoA opens read-only with its PDF downloadable; the drill-down lands in the same professional view, not a separate report world.
- **Design conformance:** plain-language tiles, drill-down to professional queue views.
- **Dependencies:** URS-W2-017.

### 3.6 ISA-88 batch recipes (W2-6)

#### URS-W2-020 — ISA-88 recipe structure over BOM/Routing

The system shall let the technologist structure a recipe as ISA-88 unit procedures, operations and phases layered over the anchor BOM + Routing pair (BOM-RW-CHM-0003-001 / RT-COMPOUND-01), without forking the anchor DocTypes.

- **Priority:** Must
- **Lineage:** Rebuild (white space — dossier §6.3, ch. G "ISA-88: Absent" in all three) · ADR-006/CDM-04 (governed BOM+Routing pair) · CONSOLIDATION.md `recipe_isa88`
- **Acceptance criteria:**
  - AC-1: Given BOM-RW-CHM-0003-001 with routing RT-COMPOUND-01, When T. Schmid defines unit procedure "Mischen" (work centre LINE-1/MIX-01) with phases "Dosieren Basisharz", "Dosieren Additiv", "Mischen 30 min", and unit procedure "Abfüllen" (LINE-1/FILL-01), Then the recipe persists the hierarchy recipe → unit procedure → phase with material assignments per phase (Basisharz 480 kg to Dosieren Basisharz, Additiv K7 20 kg to Dosieren Additiv).
  - AC-2: Given the recipe of AC-1, When the anchor BOM is inspected, Then its schema is unchanged (ISA-88 structure lives in `recipe_isa88` module DocTypes referencing BOM/Routing).
  - AC-3: Given a phase referencing a material not present in the BOM, When the recipe is checked, Then validation fails naming the phase and material.
- **Dependencies:** W1-4 recipe governance (URS-W1-xxx — gov_state); ADR-006 sign-off.

#### URS-W2-021 — Recipe scaling

The system shall scale a recipe's phase material quantities and declared output proportionally to a target batch size, with UoM-safe rounding and validation that scaled quantities stay within declared equipment limits.

- **Priority:** Must
- **Lineage:** Rebuild (white space) · wave exit criterion "recipe scaling functional" (`docs/waves/W2-traceability-quality.md`)
- **Acceptance criteria:**
  - AC-1: Given the recipe of URS-W2-020 declared for 500 kg output (480 kg Basisharz + 20 kg Additiv K7), When T. Schmid scales it to 250 kg for PO-2026-0002, Then phase quantities become 240 kg and 10 kg and the scaled recipe references its source recipe and scale factor 0.5.
  - AC-2: Given MIX-01 declares a working volume maximum equivalent to 600 kg, When scaling to 750 kg is attempted, Then scaling is refused naming the phase, work centre and limit.
  - AC-3: Given a scaled quantity that would round below the item's UoM precision (e.g. 0.004 kg), When scaling is computed, Then the result is flagged for technologist confirmation rather than silently rounded to zero.
- **Dependencies:** URS-W2-020.

#### URS-W2-022 — Recipes execute under governance

The system shall permit production orders to reference only recipes whose governance state (gov_state) is Accepted; scaling produces a new governed recipe version in Draft.

- **Priority:** Must
- **Lineage:** Rebuild wired to Absorb · ADR-006/CDM-04 ("orders may only reference Accepted recipes"); Qcadoo `TechnologyState.java:33-66` semantics via W1-4
- **Acceptance criteria:**
  - AC-1: Given a scaled recipe in gov_state Draft, When a production order accept referencing it is attempted, Then the accept gate refuses naming the recipe and its gov_state.
  - AC-2: Given the scaled recipe passes validators and is Accepted, When PO-2026-0002 references it and is accepted, Then the order proceeds and the recipe's `in_use_lock` prevents structural edits.
- **Dependencies:** URS-W2-020, URS-W2-021; W1-4 (URS-W1-xxx).

### 3.7 Hazmat / regulatory master data (W2-7)

#### URS-W2-023 — Hazmat profile on Item/Batch

The system shall provide a Hazmat Profile (UN number, SDS reference, storage class) linkable from Item and Batch, maintained by the technologist.

- **Priority:** Must
- **Lineage:** Rebuild (white space — dossier §6.3; ch. G "Hazmat: Absent" ×3, searches documented) · CDM-01 `hazmat_profile` field · CONSOLIDATION.md `regulatory_hazmat` (completes in W3)
- **Acceptance criteria:**
  - AC-1: Given T. Schmid creates hazmat profile "UN 1866 / SDS-RW-0001 / storage class 3" and links it to RW-CHM-0001, When BATCH-A-0001 is viewed, Then the profile is visible on the batch via its item (batch-level override allowed for repacked goods).
  - AC-2: Given an item flagged hazmat-mandatory without a linked profile, When a batch for it is created, Then creation is refused naming the missing profile.
  - AC-3: Given the profile of AC-1, When the SDS reference is updated, Then the change is version-audited (user, timestamp, before/after).
- **Dependencies:** W0-2 master data (URS-W0-xxx); boundary/label data explicitly deferred to W3-6.

#### URS-W2-024 — Hazmat visibility in warehouse and trace views

The system shall display the storage class and UN number wherever a hazmat batch appears in warehouse screens and the Trace Ribbon.

- **Priority:** Should
- **Lineage:** Rebuild · dossier §6.3; design skill density rules (nothing hides on desktop)
- **Acceptance criteria:**
  - AC-1: Given BATCH-A-0001 with the profile of URS-W2-023, When it renders in the RM Lager Nord stock view and the Trace Ribbon, Then storage class 3 and UN 1866 render as data columns/chips, not behind progressive disclosure.
- **Design conformance:** nothing hides on desktop; mono identifiers; density.
- **Dependencies:** URS-W2-023, URS-W2-003.

### 3.8 Warehouse fidelity completion (W2-8)

#### URS-W2-025 — Pallet balances

The system shall provide per-location pallet balances (handling units by storage location and type) reconciled against handling-unit content records.

- **Priority:** Should
- **Lineage:** Absorb · Qcadoo material-flow-resources · `palletBalance.xml` (dossier ch. 3.1 §B.3 evidence); ADR-005/CDM-03 Handling Unit
- **Acceptance criteria:**
  - AC-1: Given HU-000123 (pallet) holding 20 × 25 kg sacks of BATCH-A-0001 at NORD-A-01-01, When W. Braun opens the pallet balance for RM Lager Nord, Then HU-000123 appears at NORD-A-01-01 with its content (RW-CHM-0001, BATCH-A-0001, 500 kg).
  - AC-2: Given the sum of HU contents diverges from Bin quantity for an item/warehouse, When the reconciliation report runs, Then the divergent rows are listed (single-truth constraint: ledger is truth, HU is reference — CDM-03).
- **Dependencies:** W1-5 Handling Unit/Storage Location DocTypes (URS-W1-xxx).

#### URS-W2-026 — Stocktaking journey

The system shall provide a stocktaking journey with its own workflow (draft → in progress → accepted) generating correcting stock movements on acceptance, honouring the warehouse's disposal algorithm for count-sheet ordering.

- **Priority:** Should
- **Lineage:** Absorb · Qcadoo `StocktakingState.java`; `ResourceManagementServiceImpl.java:1015-1027` (algorithm-ordered selection) · W2-8 backlog
- **Acceptance criteria:**
  - AC-1: Given a stocktaking for RM Lager Nord counting BATCH-A-0001 at 495 kg against a book quantity of 500 kg, When W. Braun accepts the stocktaking, Then a correcting issue of 5 kg posts against BATCH-A-0001 and the stocktaking becomes immutable.
  - AC-2: Given a stocktaking in progress, When a second stocktaking for the same warehouse is created, Then creation is refused (one open stocktaking per warehouse).
- **Dependencies:** URS-W2-025; W1-5 (URS-W1-xxx).

#### URS-W2-027 — Repacking journey

The system shall provide a repacking journey that splits/merges batch quantities across handling units, preserving batch identity via `parent_batch` lineage where a new lot identity is created.

- **Priority:** Should
- **Lineage:** Absorb · Qcadoo `RepackingState.java` · CDM-01 `parent_batch` ("split/repack lineage, distinct from genealogy")
- **Acceptance criteria:**
  - AC-1: Given 500 kg of BATCH-A-0001 on HU-000123, When W. Braun repacks 100 kg onto a new handling unit, Then stock reflects 400/100 kg on the two HUs and batch identity BATCH-A-0001 is unchanged.
  - AC-2: Given a repack that creates a new lot identity (e.g. re-drumming with new labelling), When it is accepted, Then the new batch carries `parent_batch` = BATCH-A-0001, and the Trace Ribbon renders the split as lineage distinct from production genealogy.
- **Dependencies:** URS-W2-025, URS-W2-005.

### 3.9 Multi-level trace demonstration (W2-9) and e-signature decision (W2-10)

#### URS-W2-028 — Multi-level trace acceptance demonstration

The system shall demonstrably produce a full forward and backward trace across at least three genealogy levels including blocked-batch propagation, executed as a scripted acceptance scenario on the shared fixtures.

- **Priority:** Must
- **Lineage:** Wave exit criterion · `docs/waves/W2-traceability-quality.md` W2-9 · dossier §5.3 "Trace a defect batch" journey
- **Acceptance criteria:**
  - AC-1: Given the fixture chain supplier batch → BATCH-A-0002 → BATCH-C-1001/BATCH-C-1002, When the demo script blocks BATCH-A-0002 and runs forward trace, Then both FG batches are found with advisories, and backward trace from BATCH-C-1001 reaches the supplier batch — all levels, both directions, with quantities.
  - AC-2: Given the demo run, When it completes, Then its output (trace listings + ribbon screenshots) is attached to the wave acceptance record.
- **Dependencies:** URS-W2-001…004, URS-W2-009.

#### URS-W2-029 — E-signature decision record

The programme shall record the e-signature decision for compliance-critical transitions (which qa_state/exec_state/gov_state transitions and CoA issue require e-signatures vs audit trail only), as a signed-off decision record before wave exit.

- **Priority:** Must
- **Lineage:** Decision / Rebuild (white space — dossier §6.3 "Electronic signatures: no e-signature construct in any repo"; audit findings ch. 3.1/3.2/3.3 §E) · plan D3 ("Business sign-off Q2: which transitions legally require e-signatures") — **Business sign-off required**
- **Acceptance criteria:**
  - AC-1: Given the decision workshop output, When the decision record is committed (ADR or plan appendix), Then it lists per governed transition (at minimum: Blocked⇄Released, CoA issue, recipe Accept) whether an e-signature is required, and names the sign-off authority and date.
  - AC-2: Given the decision requires e-signatures for any transition, When W2 exits, Then the enforcement-point design (where the hook intercepts, what is captured) is documented and scheduled — implementation itself may land later per the decision.
- **Dependencies:** URS-W2-006, URS-W2-017, URS-W2-022.

### 3.10 Data migration requirements (open batches & genealogy history)

#### URS-W2-030 — Qcadoo dual-model merge into canonical Batch

The migration shall merge Qcadoo's dual batch model — genealogy `Batch` records and warehouse `Resource.batch` strings — into canonical Batches: conventionally-linked pairs merge into one Batch with both legacy refs; unmatched resource strings create identity-only Batches flagged `genealogy_incomplete`.

- **Priority:** Must
- **Lineage:** Absorb migration · ADR-003 consequences; CDM-01 source mapping (`batch_id` row: "dual model collapsed; conventionally-linked pairs merged at migration") · dossier §5.2 batch/lot row; assumption A6
- **Source→canonical mapping reference:** CDM-01 mapping table (`docs/canonical-model/README.md` §CDM-01): `advancedGenealogy.Batch.number` + `Resource.batch` → `batch_id`; `BatchState` TRACKED→Released, BLOCKED→Blocked, `Resource.blockedForQualityControl`→Quarantined → `qa_state`; `Resource.expirationDate` → `expiry_date` (lot→batch: earliest wins, conflicts reported).
- **Acceptance criteria:**
  - AC-1: Given a pilot extract with a genealogy Batch "GB-100" linked by convention to resource strings "GB-100", When migration runs, Then exactly one canonical Batch exists with both refs in `legacy_refs` and `genealogy_incomplete = false`.
  - AC-2: Given a resource string "RB-ORPHAN" with no genealogy Batch, When migration runs, Then an identity-only Batch is created with `genealogy_incomplete = true`.
  - AC-3: Given two resource lots of one merged batch with expiry dates 30.06.2026 and 31.07.2026, When migration runs, Then canonical `expiry_date` = 30.06.2026 and the conflict is listed on the migration report.
- **Reconciliation criteria:** batch counts — canonical batch count = distinct(genealogy batches ∪ resource batch strings) after merge-pair dedup, reported per plant; qa_state distribution reconciled against legacy state counts (TRACKED/BLOCKED/blockedForQualityControl); 100-record random spot-check comparing legacy field values to canonical fields with zero unexplained mismatches; checksum on (batch_id, item, expiry_date) tuples between staging and target.
- **Rollback condition:** if reconciliation counts diverge > 0 batches unexplained, or the spot-check finds any field-level corruption, the migration batch is rolled back (canonical Batches created by the run are deleted by run-id) and the run is repeated after correction; no partial acceptance.
- **Dependencies:** W0-5 migration tooling (URS-W0-xxx); URS-W2-005.

#### URS-W2-031 — Genealogy history migration

The migration shall load Qcadoo TrackingRecord history (including archived `arch_*` orders in W4 backfill scope, pilot subset in W2) as genealogy links on canonical Batches, and record the OFBiz trace-boundary date for Plant B history.

- **Priority:** Must
- **Lineage:** Absorb migration · CDM-01 `genealogy_links` mapping ("= TrackingRecord used/produced tree"); ADR-003 consequences ("OFBiz history carries a recorded trace-boundary") · dossier §7 implication 9; §8.2 Q2/Q3
- **Source→canonical mapping reference:** CDM-01 `genealogy_links` row (Qcadoo `=` TrackingRecord; ERPNext `≈` SLE + Serial and Batch Bundle joins; OFBiz `≈` `WorkEffortInventoryAssign/-Produced` where lotId present).
- **Acceptance criteria:**
  - AC-1: Given a pilot TrackingRecord set (produced batch, used batches, quantities), When migration runs, Then each produced batch carries consumed links matching the used-batch rows one-to-one with quantities preserved.
  - AC-2: Given Plant B history where `lotId` is absent on consumed inventory, When migration runs, Then the produced batch is flagged `genealogy_incomplete` and the plant-wide trace-boundary date is recorded in the migration register.
- **Reconciliation criteria:** link counts — target consumed/produced link count = source TrackingRecord used/produced row count (per plant, per direction); orphan check — zero genealogy links referencing non-existent batches; spot-check of 50 randomly selected trees comparing full backward trace legacy-vs-target with identical node sets.
- **Rollback condition:** any orphan link, or tree spot-check divergence, rolls back the genealogy-link load by run-id (batches from URS-W2-030 are retained); rerun after correction.
- **Dependencies:** URS-W2-030; W0-5 (URS-W0-xxx).

#### URS-W2-032 — Legacy quality flags migrate as qa_state history

The migration shall carry legacy quality flags (Qcadoo `qualityRating`/`blockedForQualityControl`, OFBiz `quantityRejected`) as qa_state history/notes only — no parametric inspection backfill.

- **Priority:** Must
- **Lineage:** Adopt-boundary migration rule · ADR-009 consequences ("No parametric backfill … legacy quality flags migrate as QA-state history"); CDM-07 mapping
- **Acceptance criteria:**
  - AC-1: Given a migrated batch whose legacy resource had `blockedForQualityControl = true`, When migration completes, Then the batch's qa_state is Quarantined and a history entry cites the legacy flag as origin.
  - AC-2: Given migrated data, When the Quality Inspection list is queried for pre-migration dates, Then no synthetic parametric inspections exist (zero backfilled QI records).
- **Reconciliation criteria:** count of Quarantined/Blocked migrated batches = count of legacy flagged resources/batches per plant; zero QI records with inspection date before the migration cut date.
- **Rollback condition:** qa_state distribution mismatch beyond zero unexplained rows rolls back the state-assignment step by run-id.
- **Dependencies:** URS-W2-030.

## 4. Non-functional requirements

#### URS-W2-033 — Trace and scan performance

The system shall render a Trace Ribbon of up to 200 nodes with UI feedback < 100 ms and server-confirmed data ≤ 2 s; scan-to-confirmation on batch identification screens shall be ≤ 300 ms server-confirmed with UI feedback < 100 ms.

- **Priority:** Must
- **Lineage:** Rebuild NFR · design skill "No dead air" (<100 ms feel, progress on control, gated actions server-confirmed); shared NFR baseline from the programme brief
- **Acceptance criteria:**
  - AC-1: Given a fixture genealogy of 200 nodes, When the ribbon opens on the reference test environment, Then p95 server response ≤ 2 s over 20 runs and the control shows progress beyond 100 ms.
  - AC-2: Given a terminal issue screen, When BATCH-A-0001 is scanned 50 times in test, Then p95 scan-to-server-confirmation ≤ 300 ms and every scan gives full-row visual + audible confirmation.
- **Design conformance:** scanner first-class input; no optimistic UI for gated actions.

#### URS-W2-034 — Audit of gated quality actions

The system shall write an audit record (user, timestamp, rule id, record ids, outcome, reason where mandatory) for every qa_state transition, QI gate refusal, blocked-consumption refusal, CoA issue, and migration run.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo `*StateChange` audit pattern (`orderStateChange.xml:36-47`, equivalents for batch) + anchor `track_changes` · dossier ch. 3.1/3.2 §E
- **Acceptance criteria:**
  - AC-1: Given the block of BATCH-A-0002 (URS-W2-006 AC-3), When the audit log is queried, Then one entry exists with user Q. Fischer, the reason text, and before/after qa_state.
  - AC-2: Given the gate refusal of URS-W2-011 AC-1, When the audit log is queried, Then the refusal is logged with rule id and record ids (refusals are logged, never toast-only).

#### URS-W2-035 — German-first i18n and locale formats

The system shall externalize all W2 UI strings with German as first language, render dates DD.MM.YYYY and quantities in kg (locale-correct), with no string concatenation.

- **Priority:** Must
- **Lineage:** Adopt platform i18n + design skill "Content and language" · ERPNext `de.po` evidence (dossier ch. 3.2 §F #46)
- **Acceptance criteria:**
  - AC-1: Given the German locale, When the Trace Ribbon, inspection queue and CoA render, Then all labels come from externalized catalogues (spot-check: zero hardcoded English literals in W2 templates) and BATCH-A-0001's expiry renders "31.12.2026".
  - AC-2: Given a quantity of 480 kg, When it renders in any W2 table, Then the numeral is tabular, right-aligned, with unit kg.

#### URS-W2-036 — Access control on W2 transitions

The system shall enforce workflow-state-level permissions: qa_state transitions restricted to the quality-inspector role; CoA issue to the quality inspector; recipe Accept to the technologist reviewer role; stocktaking acceptance to the warehouse clerk; enforced server-side.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo per-transition roles (dossier §7 implication 7; ch. 3.1 §B.2) expressed in Frappe RBAC per W1-8
- **Acceptance criteria:**
  - AC-1: Given O. Weber's operator role, When each restricted action above is attempted via API, Then each is refused with a permission error and audited; When performed by the mapped role, each succeeds.
  - AC-2: Given B. Vogel (business viewer), When any W2 screen renders, Then all data is readable but every state-changing action is absent/disabled.
- **Dependencies:** W1-8 (URS-W1-xxx).

## 5. Wave exit criteria (decomposed)

Restated from `docs/waves/W2-traceability-quality.md` ("full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional") and plan M2:

| ID | Check | Verified by |
|---|---|---|
| EXIT-W2-1 | Full multi-level (≥3 level) forward + backward trace demonstrable on fixtures, including blocked-batch propagation and `genealogy_incomplete` advisories | URS-W2-028 demo; TST TC-W2 acceptance checklist |
| EXIT-W2-2 | CoA generated from accepted inspection results for a fixture batch, immutable snapshot with PDF, refused where no accepted inspection exists | URS-W2-017 |
| EXIT-W2-3 | Recipe scaling functional: ISA-88 recipe scaled 500 kg → 250 kg with limit validation, executable only when gov_state Accepted | URS-W2-020…022 |
| EXIT-W2-4 | Pilot migration of open batches + genealogy history reconciles (counts, spot-checks, checksums) with zero unexplained divergence and documented rollback rehearsed once | URS-W2-030…032 |
| EXIT-W2-5 | E-signature decision record signed off and committed | URS-W2-029 |
| EXIT-W2-6 | All W2 UI-bearing requirements pass design-conformance review (Desk/Terminal, keyboard/scanner paths, pills, gate-refusal modals, German-first) | Design-conformance TCs |

## 6. Untraceable / deferred

- **Equipment working-volume limits for scaling (URS-W2-021 AC-2):** no legacy source models equipment limits (work centres are Workstation/FixedAsset records without capacity-volume semantics — CDM-08). The limit fields are net-new master data; values require business input. Deferred to master-data collection; the validation mechanism itself is in scope.
- **QC-exempt item list (URS-W2-006):** which items skip Quarantined-at-creation has no legacy precedent (ERPNext batches are stateless; Qcadoo blocking is manual). Requires business sign-off; flagged on URS-W2-006.
- **Plant A genealogy population completeness (dossier §8.2 Q2) and Plant B lot coverage (Q3):** open questions that size `genealogy_incomplete` volumes; the mechanism (URS-W2-004/030/031) is fully specified, the expected data quality is not — must be answered before W2 exit per waves README rule 3.
- **Sizing note:** 36 requirements — within the 25–40 guide for W2.
