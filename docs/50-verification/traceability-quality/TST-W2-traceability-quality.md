# TST W2 — Traceability & Quality

**Programme:** Rheinwerk Chemie GmbH — MES consolidation
**Wave:** W2 (Traceability & Quality)
**Document type:** Test & Verification specification
**Verifies:** `docs/20-requirements/traceability-quality/URS-W2-traceability-quality.md` (URS-W2-001…036)

---

## 1. Test strategy

**Test levels** (unit testing assumed within the implementation Definition of Done, not re-specified here):

- **Integration** — hook/workflow behaviour across DocTypes (qa_state ↔ QI ↔ exec_state, genealogy link writes on postings, picking exclusion in reservations), executed via the Frappe test harness against a seeded site.
- **Journey / acceptance** — persona journeys end-to-end through the UI (inspection queue, terminal consumption with scanner, Trace Ribbon browsing, CoA issue), scripted with fixtures below.
- **Migration reconciliation** — pilot extracts from Qcadoo (Plant A) and OFBiz (Plant B) loaded through the W0-5 tooling; counts/checksums/spot-checks per URS-W2-030…032; one rehearsed rollback.
- **Characterization-parity** — target behaviour asserted against the legacy characterization baseline (W0-6 harness) for every Absorb requirement; deliberate deviations asserted in their *new* behaviour and cross-referenced to sign-off (Section 4).
- **NFR** — latency measurements (p95 over fixed run counts), audit-log completeness queries, i18n catalogue scans, RBAC negative tests via API.
- **Design-conformance** — screen review against `.agents/skills/rheinwerk-mes-design/SKILL.md` Definition of done, plus automatable checks (contrast, keyboard path, pill composition, modal refusals).

**Environments:** `TEST-W2` (integration/journey; seeded fixture site, Terminal-mode station profile available for shop-floor cases), `MIG-PILOT` (migration; staging DB with Plant A/B pilot extracts at the pinned dossier commits), `PERF` (NFR latency, reference hardware profile).

**Test data strategy:** the shared Rheinwerk fixtures are authoritative and reset before each suite: products RW-CHM-0001 "Rheinol 40 Basisharz" (25 kg sack), RW-CHM-0002 "Additiv K7" (5 kg pail), RW-CHM-0003 "Rheinol 40 Compound" (FG); raw batches BATCH-A-0001 (500 kg, expiry 31.12.2026), BATCH-A-0002 (50 kg, expiry 30.06.2026, blocked mid-suite); FG batches BATCH-C-1001, BATCH-C-1002; orders PO-2026-0001 (500 kg on LINE-1), PO-2026-0002; work centres LINE-1/MIX-01, LINE-1/FILL-01; warehouses RM Lager Nord (FEFO), FG Lager Süd (FIFO); storage location NORD-A-01-01; handling unit HU-000123; recipe BOM-RW-CHM-0003-001 + routing RT-COMPOUND-01; QI template QIT-COMPOUND (viscosity 1200–1400 mPa·s, density 1.02–1.06 g/cm³, moisture ≤ 0.5 %). Personas: P. Krüger (planner, fixture context only), O. Weber (operator), Q. Fischer (quality inspector), W. Braun (warehouse clerk), T. Schmid (technologist), B. Vogel (business viewer). A three-level trace fixture adds supplier batch SUP-K7-0001 (Additiv K7 supplier lot feeding BATCH-A-0002).

## 2. Traceability matrix

Every URS-W2 requirement maps to ≥1 test case; every TC maps back. No orphans.

| URS | Test cases | | URS | Test cases |
|---|---|---|---|---|
| URS-W2-001 | TC-W2-001, TC-W2-002 | | URS-W2-019 | TC-W2-027 |
| URS-W2-002 | TC-W2-003 | | URS-W2-020 | TC-W2-028 |
| URS-W2-003 | TC-W2-004, TC-W2-005 | | URS-W2-021 | TC-W2-029 |
| URS-W2-004 | TC-W2-006 | | URS-W2-022 | TC-W2-030 |
| URS-W2-005 | TC-W2-007, TC-W2-008 | | URS-W2-023 | TC-W2-031 |
| URS-W2-006 | TC-W2-009, TC-W2-010 | | URS-W2-024 | TC-W2-032 |
| URS-W2-007 | TC-W2-011 | | URS-W2-025 | TC-W2-033 |
| URS-W2-008 | TC-W2-012, TC-W2-040 | | URS-W2-026 | TC-W2-034 |
| URS-W2-009 | TC-W2-013 | | URS-W2-027 | TC-W2-035 |
| URS-W2-010 | TC-W2-014, TC-W2-015 | | URS-W2-028 | TC-W2-036 |
| URS-W2-011 | TC-W2-016, TC-W2-041 | | URS-W2-029 | TC-W2-037 |
| URS-W2-012 | TC-W2-017 | | URS-W2-030 | TC-W2-042, TC-W2-043 |
| URS-W2-013 | TC-W2-018, TC-W2-019 | | URS-W2-031 | TC-W2-044 |
| URS-W2-014 | TC-W2-020, TC-W2-021 | | URS-W2-032 | TC-W2-045 |
| URS-W2-015 | TC-W2-022 | | URS-W2-033 | TC-W2-046, TC-W2-047 |
| URS-W2-016 | TC-W2-023 | | URS-W2-034 | TC-W2-048 |
| URS-W2-017 | TC-W2-024, TC-W2-025 | | URS-W2-035 | TC-W2-049 |
| URS-W2-018 | TC-W2-026 | | URS-W2-036 | TC-W2-050 |

Reverse check: TC-W2-001…050 each cite their URS in Section 3; parity cases TC-W2-038…041 additionally serve Section 4. TC-W2-038/039 verify parity aspects of URS-W2-006 and URS-W2-010 respectively.

## 3. Test cases

Format: objective · URS link(s) · preconditions & fixtures · steps (expected result per step) · pass/fail rule · type tag.

### 3.1 Genealogy (W2-1)

**TC-W2-001 — Genealogy links written at output recording** — *Integration*
- URS: URS-W2-001 (AC-1)
- Preconditions: PO-2026-0001 In Progress; BATCH-A-0001 (480 kg staged), BATCH-A-0002 (20 kg staged) Released.
- Steps: 1) As O. Weber, record consumption 480 kg BATCH-A-0001 → posting accepted. 2) Record consumption 20 kg BATCH-A-0002 → posting accepted. 3) Record output creating BATCH-C-1001 → batch created Quarantined. 4) Query BATCH-C-1001 genealogy_links → two `consumed` links (480 kg / 20 kg) + one `produced` link to PO-2026-0001.
- Pass: link set exactly as step 4, quantities exact. Fail otherwise.

**TC-W2-002 — Genealogy survives cancel/repost; no links for non-batch materials** — *Integration*
- URS: URS-W2-001 (AC-2, AC-3)
- Preconditions: TC-W2-001 executed; BOM includes non-batch-managed process water.
- Steps: 1) Cancel and repost the BATCH-A-0002 consumption entry with corrected qty 21 kg → genealogy link updated to 21 kg in the same transaction. 2) Run genealogy-vs-SLE reconciliation query → zero divergent rows. 3) Inspect BATCH-C-1001 links → no link for process water; `genealogy_incomplete = false`.
- Pass: all three expected results hold.

**TC-W2-003 — Forward/backward multi-level browse** — *Journey*
- URS: URS-W2-002 (AC-1…3)
- Preconditions: chain SUP-K7-0001 → BATCH-A-0002 → {BATCH-C-1001 (PO-2026-0001), BATCH-C-1002 (PO-2026-0002)} loaded.
- Steps: 1) As Q. Fischer open backward trace of BATCH-C-1001 → BATCH-A-0001 and BATCH-A-0002 at level 1 with quantities. 2) Expand level 2 → SUP-K7-0001 appears; no node visited twice. 3) Open forward trace of BATCH-A-0002 → BATCH-C-1001 and BATCH-C-1002 with their production orders.
- Pass: node sets and quantities exactly match fixtures; no cycles/duplicates.

**TC-W2-004 — Trace Ribbon rendering and interaction** — *Design-conformance / Journey*
- URS: URS-W2-003 (AC-1, AC-3)
- Preconditions: TC-W2-003 fixture; Desk mode.
- Steps: 1) As B. Vogel open the ribbon for BATCH-C-1001 → suppliers left, focus centred, downstream right. 2) Tab/arrow to the BATCH-A-0001 chip and press Enter → ribbon re-centres on BATCH-A-0001, prior expansion state retained. 3) Verify chips: mono ID (IBM Plex Mono), status dot, one-click/Enter to ribbon. 4) Press `?` → shortcut sheet opens.
- Pass: all four steps conform to design skill pattern 4 + component rules.

**TC-W2-005 — Ribbon blocked-branch break and print parity** — *Design-conformance*
- URS: URS-W2-003 (AC-2, AC-4)
- Preconditions: BATCH-A-0002 Blocked (via TC-W2-009).
- Steps: 1) Render ribbon for BATCH-C-1001 → BATCH-A-0002 branch in `--rw-signal-red` with hard visual break; pill = icon + label "Blocked" + colour. 2) Invoke print → printed structure identical; blocked state identifiable without colour (icon + label present).
- Pass: both hold; colour-only signalling anywhere = fail.

**TC-W2-006 — genealogy_incomplete advisory** — *Integration / Design-conformance*
- URS: URS-W2-004 (AC-1, AC-2)
- Preconditions: migrated identity-only batch RB-ORPHAN (from TC-W2-043) present in a trace chain.
- Steps: 1) Open RB-ORPHAN → `genealogy_incomplete = true`. 2) Render it in a backward trace → amber advisory pill "Trace incomplete"; trace does not silently terminate. 3) For a Plant B-boundary batch, verify the trace-boundary date is displayed.
- Pass: flag, pill and boundary date all render.

### 3.2 Unified batch (W2-2)

**TC-W2-007 — Canonical batch creation with all four facets** — *Integration*
- URS: URS-W2-005 (AC-1, AC-2)
- Steps: 1) As T. Schmid create BATCH-A-0001 (RW-CHM-0001, 500 kg, expiry 31.12.2026) → saved with batch_id, item, qty_original 500 kg, expiry 31.12.2026, qa_state Quarantined. 2) Create a batch for a shelf-life item without expiry → save refused naming expiry_date.
- Pass: both results exact.

**TC-W2-008 — Anchor Batch DocType not forked** — *Integration*
- URS: URS-W2-005 (AC-3)
- Steps: 1) Diff the deployed anchor Batch schema against upstream anchor → zero core-field modifications; extensions present only as custom fields / linked DocTypes.
- Pass: schema diff clean.

**TC-W2-009 — qa_state workflow transitions and reasons** — *Integration*
- URS: URS-W2-006 (AC-1…3, AC-5)
- Steps: 1) Produce BATCH-C-1001 → qa_state Quarantined. 2) Accept its QIT-COMPOUND inspection → qa_state Released automatically; audit entry with triggering inspection. 3) As Q. Fischer block BATCH-A-0002 without reason → refused; with reason "supplier recall K7/2026-06" → Blocked, reason audited. 4) Attempt Released → Quarantined via API → rejected naming allowed transitions.
- Pass: all four steps exact.

**TC-W2-010 — qa_state role gate** — *Integration / NFR*
- URS: URS-W2-006 (AC-4); URS-W2-036 overlap
- Steps: 1) As O. Weber attempt unblock of BATCH-A-0002 via UI and API → both refused with permission error, audited. 2) As Q. Fischer unblock with reason → Released.
- Pass: refusal + success as specified.

**TC-W2-011 — Legacy refs and legacy-bridge hover** — *Migration / Design-conformance*
- URS: URS-W2-007 (AC-1, AC-2)
- Preconditions: migrated batch merged from "GB-4711"/"RB-4711" (MIG-PILOT).
- Steps: 1) Open the batch → legacy_refs lists both Qcadoo refs verbatim. 2) Hover the expiry_date label → "was: Resource.expirationDate → now: expiry_date". 3) Toggle the post-cutover feature flag → affordance removed.
- Pass: all three hold.

**TC-W2-012 — FEFO ordering by canonical expiry** — *Integration*
- URS: URS-W2-008 (AC-1)
- Preconditions: RM Lager Nord (FEFO) holds BATCH-A-0001 (31.12.2026) + second Basisharz batch (30.09.2026).
- Steps: 1) As W. Braun pick 100 kg RW-CHM-0001 → proposal orders the 30.09.2026 batch first.
- Pass: proposal order exact.

### 3.3 Blocking & quarantine (W2-3)

**TC-W2-013 — Blocking propagation and clearance** — *Integration*
- URS: URS-W2-009 (AC-1…3)
- Preconditions: BATCH-A-0002 consumed into BATCH-C-1001 and BATCH-C-1002.
- Steps: 1) Block BATCH-A-0002 → both FG batches carry advisory "Blocked ancestor: BATCH-A-0002" in the same transaction; own qa_state unchanged. 2) Render BATCH-C-1001 chip → amber advisory pill (icon+label). 3) Unblock BATCH-A-0002 (no other blocked ancestor) → advisories cleared.
- Pass: propagation, rendering and clearance all exact.

**TC-W2-014 — Picking exclusion of Blocked/Quarantined stock** — *Integration*
- URS: URS-W2-010 (AC-1, AC-2)
- Steps: 1) With BATCH-A-0002 Blocked, create a pick for 5 kg RW-CHM-0002 → BATCH-A-0002 absent; as sole stock, pick fails naming the blocked batch. 2) With BATCH-C-1001 Quarantined, attempt reservation for RW-CHM-0003 → quantity not reservable; availability excludes it.
- Pass: both exclusions enforced.

**TC-W2-015 — Terminal gate refusal on blocked HU scan** — *Journey / Design-conformance*
- URS: URS-W2-010 (AC-3)
- Preconditions: Terminal mode station; HU-000123 contains Blocked stock.
- Steps: 1) As O. Weber scan HU-000123 at the issue screen → modal (not toast) naming rule (blocked-batch exclusion), record (BATCH-A-0002, HU-000123), resolution (QA unblock required). 2) Check audit log → refusal logged. 3) Esc closes modal; scan field regains focus.
- Pass: modal content, logging and keyboard behaviour all conform.

**TC-W2-016 — Blocked-batch consumption refused (UI + API)** — *Integration / Journey*
- URS: URS-W2-011 (AC-1, AC-2)
- Steps: 1) On PO-2026-0002, scan BATCH-A-0002 (Blocked) for consumption → gate-refusal modal (rule/record/resolution); no genealogy link written. 2) POST the same consumption via API → server hook refuses with the same rule identifier.
- Pass: both layers refuse; zero links written.

**TC-W2-017 — Quarantine location putaway and movement gate** — *Integration*
- URS: URS-W2-012 (AC-1, AC-2)
- Steps: 1) Receive BATCH-C-1001 (Quarantined) → putaway proposal targets NORD-A-01-01 (quarantine-flagged). 2) As O. Weber attempt transfer out → refused (role gate). 3) Release the batch; as W. Braun transfer out → posts.
- Pass: all three exact.

### 3.4 Quality Inspection (W2-4)

**TC-W2-018 — Template instantiation and auto-accept** — *Integration*
- URS: URS-W2-013 (AC-1, AC-2)
- Steps: 1) As Q. Fischer create In Process inspection for BATCH-C-1001 from QIT-COMPOUND → three parameters with limits instantiated. 2) Enter viscosity 1290 mPa·s, density 1.04 g/cm³, moisture 0.3 % → all readings pass; result Accepted automatically.
- Pass: instantiation and auto-result exact.

**TC-W2-019 — Out-of-limit reading auto-rejects** — *Integration*
- URS: URS-W2-013 (AC-3)
- Steps: 1) Enter viscosity 1450 mPa·s → inspection Rejected; failing parameter and limit identified on the reading row.
- Pass: rejection + identification exact.

**TC-W2-020 — QI gate blocks completion (missing/rejected)** — *Integration / Journey*
- URS: URS-W2-014 (AC-1, AC-2)
- Steps: 1) With no submitted inspection, attempt completion of PO-2026-0001 → modal names rule (QI-required), record (PO-2026-0001, BATCH-C-1001, QIT-COMPOUND), resolution; exec_state stays In Progress. 2) With a Rejected inspection, attempt completion → refusal names the Rejected inspection.
- Pass: both refusals with full rule/record/resolution; exec_state unchanged.

**TC-W2-021 — Accepted QI releases batch and permits completion** — *Integration*
- URS: URS-W2-014 (AC-3)
- Steps: 1) Accept the inspection → BATCH-C-1001 qa_state Released. 2) Complete PO-2026-0001 → exec_state Completed.
- Pass: both transitions occur, audited.

**TC-W2-022 — Inspection queue journey** — *Journey / Design-conformance*
- URS: URS-W2-015 (AC-1…3)
- Steps: 1) With inspections due for BATCH-C-1001/1002, open the queue → both rows with batch chip, item, type; arrows move selection; Enter opens detail. 2) Enter readings → units suffixed in inputs; inline validation on blur; failed submit preserves entries. 3) Clear the queue → empty state directs ("No inspections due — next scheduled …").
- Pass: all conform to Work Queue → Detail and form rules.

**TC-W2-023 — Rejected inspection requires disposition** — *Integration*
- URS: URS-W2-016 (AC-1, AC-2)
- Steps: 1) Reject BATCH-C-1002's inspection; open disposition → choices Block batch / Assign rework, reason mandatory. 2) Record no disposition; run the integrity check → BATCH-C-1002 listed "Rejected without disposition".
- Pass: both exact.

### 3.5 CoA (W2-5)

**TC-W2-024 — CoA generation from accepted inspection** — *Integration / Journey*
- URS: URS-W2-017 (AC-1, AC-2)
- Steps: 1) With BATCH-C-1001 Released (Accepted inspection), issue CoA → certificate snapshots the three readings with limits, batch/item identity, signatory Q. Fischer, issue date; PDF attached. 2) Attempt CoA for a Quarantined batch → refused naming the missing inspection.
- Pass: both exact.

**TC-W2-025 — CoA immutability and versioning** — *Integration*
- URS: URS-W2-017 (AC-3)
- Steps: 1) Amend/cancel the underlying inspection after issue → CoA snapshot unchanged. 2) Issue a new CoA version → prior version marked superseded, both retrievable.
- Pass: immutability + versioning hold.

**TC-W2-026 — Ribbon embedded in CoA** — *Design-conformance*
- URS: URS-W2-018 (AC-1)
- Steps: 1) View the CoA for BATCH-C-1001 → embedded ribbon node/state set identical to the standalone ribbon at the same instant; print rendering icon+label-safe.
- Pass: identical structure.

**TC-W2-027 — Business retrieval of CoA** — *Journey*
- URS: URS-W2-019 (AC-1)
- Steps: 1) As B. Vogel search "BATCH-C-1001" from the Command Dashboard → CoA opens read-only, PDF downloadable, within the professional view.
- Pass: retrieval without state-changing affordances.

### 3.6 ISA-88 recipes (W2-6)

**TC-W2-028 — ISA-88 structure over BOM/Routing** — *Integration*
- URS: URS-W2-020 (AC-1…3)
- Steps: 1) As T. Schmid define "Mischen" (MIX-01: Dosieren Basisharz 480 kg, Dosieren Additiv 20 kg, Mischen 30 min) and "Abfüllen" (FILL-01) over BOM-RW-CHM-0003-001/RT-COMPOUND-01 → hierarchy persisted with material-per-phase. 2) Diff anchor BOM schema → unchanged. 3) Add a phase referencing a material not in the BOM; check → validation fails naming phase + material.
- Pass: all three exact.

**TC-W2-029 — Scaling arithmetic, limits and rounding guard** — *Integration*
- URS: URS-W2-021 (AC-1…3)
- Steps: 1) Scale the 500 kg recipe to 250 kg → 240/10 kg, source reference + factor 0.5 recorded. 2) Scale to 750 kg with MIX-01 limit 600 kg → refused naming phase, work centre, limit. 3) Construct a scale yielding 0.004 kg → flagged for confirmation, not silently zeroed.
- Pass: all three exact.

**TC-W2-030 — Governance gate on recipe use** — *Integration*
- URS: URS-W2-022 (AC-1, AC-2)
- Steps: 1) Reference the scaled recipe (gov_state Draft) from a production-order accept → refused naming recipe + gov_state. 2) Accept the recipe (validators pass); accept PO-2026-0002 → proceeds; attempt structural edit → blocked by in_use_lock.
- Pass: both exact.

### 3.7 Hazmat (W2-7)

**TC-W2-031 — Hazmat profile lifecycle** — *Integration*
- URS: URS-W2-023 (AC-1…3)
- Steps: 1) Create profile UN 1866 / SDS-RW-0001 / storage class 3; link to RW-CHM-0001 → visible on BATCH-A-0001 via item. 2) Flag an item hazmat-mandatory without profile; create a batch → refused naming missing profile. 3) Update the SDS reference → version-audited before/after.
- Pass: all three exact.

**TC-W2-032 — Hazmat visibility in stock and ribbon** — *Design-conformance*
- URS: URS-W2-024 (AC-1)
- Steps: 1) Render RM Lager Nord stock view and the ribbon with BATCH-A-0001 → storage class 3 and UN 1866 as columns/chips, not behind disclosure.
- Pass: visible in both surfaces.

### 3.8 Warehouse fidelity completion (W2-8)

**TC-W2-033 — Pallet balance and single-truth reconciliation** — *Integration*
- URS: URS-W2-025 (AC-1, AC-2)
- Steps: 1) With HU-000123 (20 × 25 kg BATCH-A-0001 at NORD-A-01-01), open pallet balance → HU listed with location + content 500 kg. 2) Force an HU-content divergence in test data; run reconciliation → divergent rows listed against the ledger truth.
- Pass: both exact.

**TC-W2-034 — Stocktaking journey** — *Journey / Integration*
- URS: URS-W2-026 (AC-1, AC-2)
- Steps: 1) Stocktake RM Lager Nord: count BATCH-A-0001 at 495 kg vs book 500 kg; accept → correcting 5 kg issue posts; stocktaking immutable. 2) Create a second open stocktaking for the same warehouse → refused.
- Pass: both exact.

**TC-W2-035 — Repacking preserves identity / records lineage** — *Integration*
- URS: URS-W2-027 (AC-1, AC-2)
- Steps: 1) Repack 100 kg of BATCH-A-0001 to a new HU → 400/100 kg split, batch identity unchanged. 2) Repack with new lot identity → new batch has parent_batch = BATCH-A-0001; ribbon renders it as split lineage, distinct from production genealogy.
- Pass: both exact.

### 3.9 Wave demo & decision (W2-9/10)

**TC-W2-036 — Multi-level trace acceptance demo** — *Journey (wave acceptance)*
- URS: URS-W2-028 (AC-1, AC-2)
- Steps: 1) Run the scripted demo: block BATCH-A-0002; forward trace → BATCH-C-1001/1002 with advisories; backward trace from BATCH-C-1001 → SUP-K7-0001 at level 2; quantities listed. 2) Attach trace listings + ribbon screenshots to the wave acceptance record.
- Pass: three levels, both directions, propagation shown, artefacts attached.

**TC-W2-037 — E-signature decision record verification** — *NFR (documentation)*
- URS: URS-W2-029 (AC-1, AC-2)
- Steps: 1) Inspect the committed decision record → per-transition e-signature requirement listed (min. Blocked⇄Released, CoA issue, recipe Accept), sign-off authority + date named. 2) If any transition requires e-signature → enforcement-point design documented and scheduled.
- Pass: record complete and signed off.

## 4. Parity test section (Absorb scope)

Each case asserts target behaviour against the legacy characterization baseline (W0-6 harness), citing the legacy code path that is the contract. Deliberate deviations carry their sign-off reference.

| TC | Legacy contract (code path) | Assertion | Deviation? |
|---|---|---|---|
| TC-W2-038 | Qcadoo `BatchState.java:31-44` — TRACKED⇄BLOCKED reversible with reason | Blocked⇄Released reversibility + mandatory reason match legacy characterization outputs (same inputs → same accept/refuse decisions) | **Deviation:** added Quarantined entry state (no legacy counterpart) — asserted as new behaviour; sign-off ref URS-W2-006 |
| TC-W2-039 | Qcadoo `ResourceCriteriaModifiers.java:59,70` — QC-blocked resources excluded from candidate lists | For each characterization fixture (blocked lot present/absent), target picking candidate set = legacy set | **Deviation:** Quarantined also excluded (legacy exclusion is blocked-only) — sign-off ref URS-W2-006/010 |
| TC-W2-040 | ERPNext `stock_ledger_entry.py:287-299` — expired-batch consumption throw | Same-date-boundary fixtures (expiry = today, +1, −1) produce identical accept/throw decisions as the Plant C characterization baseline | Parity exact (Adopt); Plant A behaviour change governed by W1-9 sign-off |
| TC-W2-041 | Qcadoo `BatchBasicStateListenerService.java` (blocked batch unusable) + `TrackingRecordFields.java:31-49` link semantics | Consumption refusal for blocked batches and produced↔used link shape (one produced, n consumed with qty) match characterization outputs | **Deviation:** genealogy propagation advisories (URS-W2-009) have no legacy counterpart — asserted as new behaviour; sign-off ref URS-W2-009 |

- TC-W2-038 — *Parity* — URS-W2-006. Steps: replay the characterization input set for batch state transitions through the target workflow; compare decision-by-decision. Pass: zero unexplained divergence; the Quarantined additions appear only in the documented deviation list.
- TC-W2-039 — *Parity* — URS-W2-010. Steps: replay picking-candidate fixtures; compare candidate sets. Pass: legacy-equivalent for Blocked; Quarantined exclusions documented as deviation.
- TC-W2-040 — *Parity* — URS-W2-008. Steps: replay expiry boundary fixtures against target posting hook. Pass: identical decisions to Plant C baseline.
- TC-W2-041 — *Parity* — URS-W2-011, URS-W2-001. Steps: replay blocked-use and link-shape fixtures. Pass: parity except documented propagation deviation.

## 5. Migration reconciliation cases

**TC-W2-042 — Dual-model merge (matched pairs)** — *Migration*
- URS: URS-W2-030 (AC-1, AC-3 + reconciliation)
- Steps: 1) Load pilot extract with genealogy batch "GB-100" + resource strings "GB-100" (two lots, expiries 30.06.2026/31.07.2026). 2) Verify one canonical Batch, both legacy_refs, genealogy_incomplete=false, expiry 30.06.2026, conflict on report. 3) Run reconciliation: batch counts, qa_state distribution, 100-record spot-check, checksum on (batch_id, item, expiry_date).
- Pass: zero unexplained divergence on every reconciliation criterion.

**TC-W2-043 — Orphan resource strings and rollback rehearsal** — *Migration*
- URS: URS-W2-030 (AC-2 + rollback)
- Steps: 1) Load extract containing "RB-ORPHAN" → identity-only Batch with genealogy_incomplete=true. 2) Inject a deliberate count divergence; rerun → run rolled back by run-id (canonical Batches of the run removed), rollback logged. 3) Correct and rerun → clean reconciliation.
- Pass: orphan handling + rollback both demonstrated.

**TC-W2-044 — Genealogy history load and trace-boundary** — *Migration*
- URS: URS-W2-031 (AC-1, AC-2 + reconciliation/rollback)
- Steps: 1) Load pilot TrackingRecord set → consumed links match used-batch rows 1:1 with quantities. 2) Load Plant B rows lacking lotId → produced batches flagged genealogy_incomplete; trace-boundary date in the migration register. 3) Reconcile: link counts per direction/plant; zero orphan links; 50-tree spot-check legacy-vs-target. 4) Inject an orphan link → genealogy load rolls back by run-id, batches retained.
- Pass: all reconciliation criteria + rollback behaviour exact.

**TC-W2-045 — Quality flags migrate as state history only** — *Migration*
- URS: URS-W2-032 (AC-1, AC-2 + reconciliation)
- Steps: 1) Load resources with blockedForQualityControl=true → batches Quarantined with history citing the legacy flag. 2) Query QI list before the cut date → zero backfilled inspections. 3) Reconcile Quarantined/Blocked counts vs legacy flagged counts.
- Pass: zero synthetic QIs; counts reconcile exactly.

## 6. NFR & design-conformance cases

**TC-W2-046 — Trace Ribbon latency** — *NFR*
- URS: URS-W2-033 (AC-1). Steps: render a 200-node fixture ribbon 20× on PERF → p95 server ≤ 2 s; progress indicator on the control beyond 100 ms. Pass: both thresholds met.

**TC-W2-047 — Scan-to-confirmation latency** — *NFR*
- URS: URS-W2-033 (AC-2). Steps: scan BATCH-A-0001 50× at a Terminal-mode issue screen → p95 ≤ 300 ms server-confirmed; each scan gives full-row visual + audible confirmation. Pass: thresholds + confirmation behaviour met.

**TC-W2-048 — Audit completeness for gated actions** — *NFR*
- URS: URS-W2-034 (AC-1, AC-2). Steps: execute one instance each of qa_state transition, QI gate refusal, blocked-consumption refusal, CoA issue, migration run; query the audit log → each has user, timestamp, rule id, record ids, outcome, reason where mandatory. Pass: 5/5 complete entries.

**TC-W2-049 — German-first i18n and locale formats** — *NFR / Design-conformance*
- URS: URS-W2-035 (AC-1, AC-2). Steps: 1) Scan W2 templates for hardcoded literals → zero. 2) Render ribbon, queue, CoA in German → catalogue strings only; expiry "31.12.2026". 3) Verify 480 kg renders tabular, right-aligned, unit-suffixed. Pass: all hold.

**TC-W2-050 — Workflow-state-level RBAC** — *NFR*
- URS: URS-W2-036 (AC-1, AC-2). Steps: 1) As O. Weber attempt via API: qa_state transition, CoA issue, recipe Accept, stocktaking accept → all refused + audited. 2) Repeat with the mapped roles (Q. Fischer ×2, T. Schmid reviewer, W. Braun) → all succeed. 3) As B. Vogel render each W2 screen → read-only, no state-changing actions. Pass: every check exact.

## 7. Wave acceptance checklist

Executable closure of the Epic — maps EXIT-W2-N (URS §5) to test cases; all listed TCs must pass.

| Exit check | Test cases | Status gate |
|---|---|---|
| EXIT-W2-1 — multi-level trace demonstrable incl. blocking propagation + incompleteness advisories | TC-W2-001…006, TC-W2-013, TC-W2-036 | All pass; demo artefacts attached |
| EXIT-W2-2 — CoA generated from inspection results | TC-W2-018, TC-W2-024, TC-W2-025, TC-W2-026 | All pass |
| EXIT-W2-3 — recipe scaling functional under governance | TC-W2-028, TC-W2-029, TC-W2-030 | All pass |
| EXIT-W2-4 — pilot migration reconciles; rollback rehearsed | TC-W2-042…045 | All pass; one rollback rehearsal logged |
| EXIT-W2-5 — e-signature decision signed off | TC-W2-037 | Record committed |
| EXIT-W2-6 — design conformance across W2 UI | TC-W2-004, TC-W2-005, TC-W2-015, TC-W2-022, TC-W2-026, TC-W2-032, TC-W2-049 | All pass + screen review vs design skill Definition of done |
| Parity contract closed (Absorb scope) | TC-W2-038…041 | Parity exact or deviation signed off |
| NFR floor | TC-W2-046…048, TC-W2-050 | All pass |

Totals: 50 test cases (TC-W2-001…050) covering 36 requirements (URS-W2-001…036); no orphans in either direction.
