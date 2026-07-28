# TST W1 — Production Core

**Rheinwerk MES Consolidation — Test & Verification**
Wave: W1 (Production Core) · Verifies: `docs/urs/URS-W1-production-core.md` · Status: Draft for review

---

## 1. Test strategy

**Levels.** Unit tests assumed in-app (regression floor from W0). This document specifies:

- **Integration** — workflow hooks over anchor Work Order/BOM/SRE; reconciliation of `exec_state` with anchor status; HU/Storage Location referencing the ledger.
- **Journey/acceptance** — the two exit journeys: planner (create→accept→start→monitor) and operator (job cards, scanner, record output→complete), plus technologist recipe governance and warehouse clerk flows.
- **Characterisation-parity** — W0 harness contracts (URS-W0-012) executed against the W1 implementation; parity for all gates except the signed-off expiry divergence.
- **Migration reconciliation** — none: W1 lands no migrated data (URS §5); fixtures are created through W0 tooling.
- **NFR** — latency, audit/logging, i18n, access control.
- **Design-conformance** — Desk/Terminal modes, status pills, gate-refusal modals, keyboard/scanner paths, legacy bridge.

**Environments.** CI runner (automated integration/parity/NFR-scan tests) and an integration site with a Terminal-mode station profile for journey and design-conformance checks; latency tests on the terminal profile with network shaping.

**Test data.** Shared programme fixtures: items RW-CHM-0001/0002/0003; raw batches BATCH-A-0001 (Rheinol 40 Basisharz, 500 kg, expiry 31.12.2026), BATCH-A-0002 (Additiv K7, 50 kg, expiry 30.06.2026, later Blocked — used here only for expiry, `qa_state` workflow is W2); FG batches BATCH-C-1001/1002; orders PO-2026-0001 (500 kg RW-CHM-0003 on LINE-1), PO-2026-0002; work centres LINE-1/MIX-01, LINE-1/FILL-01; warehouses RM Lager Nord (FEFO), FG Lager Süd (FIFO); location NORD-A-01-01; HU-000123; BOM-RW-CHM-0003-001 + RT-COMPOUND-01. Personas: P. Krüger (planner), O. Weber (operator), T. Schmid (technologist), W. Braun (warehouse clerk), B. Vogel (business viewer).

## 2. Traceability matrix

| URS ID | Test cases | | Test case | URS ID(s) |
|---|---|---|---|---|
| URS-W1-001 | TC-W1-001, TC-W1-038 | | TC-W1-001 | URS-W1-001 |
| URS-W1-002 | TC-W1-002, TC-W1-030 | | TC-W1-002 | URS-W1-002 |
| URS-W1-003 | TC-W1-003 | | TC-W1-003 | URS-W1-003 |
| URS-W1-004 | TC-W1-004, TC-W1-005 | | TC-W1-004 | URS-W1-004 |
| URS-W1-005 | TC-W1-006, TC-W1-030 | | TC-W1-005 | URS-W1-004 |
| URS-W1-006 | TC-W1-007 | | TC-W1-006 | URS-W1-005 |
| URS-W1-007 | TC-W1-008, TC-W1-030 | | TC-W1-007 | URS-W1-006 |
| URS-W1-008 | TC-W1-009 | | TC-W1-008 | URS-W1-007 |
| URS-W1-009 | TC-W1-010 | | TC-W1-009 | URS-W1-008 |
| URS-W1-010 | TC-W1-011 | | TC-W1-010 | URS-W1-009 |
| URS-W1-011 | TC-W1-012 | | TC-W1-011 | URS-W1-010 |
| URS-W1-012 | TC-W1-013 | | TC-W1-012 | URS-W1-011 |
| URS-W1-013 | TC-W1-014 | | TC-W1-013 | URS-W1-012 |
| URS-W1-014 | TC-W1-015 | | TC-W1-014 | URS-W1-013 |
| URS-W1-015 | TC-W1-016, TC-W1-030 | | TC-W1-015 | URS-W1-014 |
| URS-W1-016 | TC-W1-017 | | TC-W1-016 | URS-W1-015 |
| URS-W1-017 | TC-W1-018 | | TC-W1-017 | URS-W1-016 |
| URS-W1-018 | TC-W1-019 | | TC-W1-018 | URS-W1-017 |
| URS-W1-019 | TC-W1-020 | | TC-W1-019 | URS-W1-018 |
| URS-W1-020 | TC-W1-021, TC-W1-030 | | TC-W1-020 | URS-W1-019 |
| URS-W1-021 | TC-W1-022 | | TC-W1-021 | URS-W1-020 |
| URS-W1-022 | TC-W1-023 | | TC-W1-022 | URS-W1-021 |
| URS-W1-023 | TC-W1-024 | | TC-W1-023 | URS-W1-022 |
| URS-W1-024 | TC-W1-025 | | TC-W1-024 | URS-W1-023 |
| URS-W1-025 | TC-W1-026 | | TC-W1-025 | URS-W1-024 |
| URS-W1-026 | TC-W1-027, TC-W1-038 | | TC-W1-026 | URS-W1-025 |
| URS-W1-027 | TC-W1-028 | | TC-W1-027 | URS-W1-026 |
| URS-W1-028 | TC-W1-029 | | TC-W1-028 | URS-W1-027 |
| URS-W1-029 | TC-W1-031 | | TC-W1-029 | URS-W1-028 |
| URS-W1-030 | TC-W1-032, TC-W1-033 | | TC-W1-030 | URS-W1-002/005/007/015/020 (parity suite) |
| URS-W1-031 | TC-W1-034 | | TC-W1-031 | URS-W1-029 |
| URS-W1-032 | TC-W1-035 | | TC-W1-032 | URS-W1-030 |
| URS-W1-033 | TC-W1-036 | | TC-W1-033 | URS-W1-030 |
| URS-W1-034 | TC-W1-037 | | TC-W1-034 | URS-W1-031 |
| URS-W1-035 | TC-W1-039 | | TC-W1-035 | URS-W1-032 |
| — | — | | TC-W1-036 | URS-W1-033 |
| — | — | | TC-W1-037 | URS-W1-034 |
| — | — | | TC-W1-038 | URS-W1-001, URS-W1-026 (exit journeys) |
| — | — | | TC-W1-039 | URS-W1-035 |

No orphans in either direction (35 URS ↔ 39 TC).

## 3. Test cases

### TC-W1-001 — `exec_state` workflow lifecycle *(Integration)*
- **Objective:** exec_state states and default. **URS:** URS-W1-001.
- **Preconditions:** W0 exit; PO-2026-0001 created (500 kg RW-CHM-0003, LINE-1, BOM-RW-CHM-0003-001 Accepted).
- **Steps:**
  1. Open PO-2026-0001 as P. Krüger. → `exec_state` = Pending; anchor Work Order unforked.
  2. Accept (dates 10.03.2026–12.03.2026 set). → Accepted.
  3. Start, then interrupt as O. Weber, then resume. → In Progress → Interrupted → In Progress.
- **Pass/fail:** each state exactly as expected; state pill shows icon+label+colour.

### TC-W1-002 — Illegal transitions refused *(Integration)*
- **Objective:** transition set matches Qcadoo `canChangeTo`. **URS:** URS-W1-002.
- **Steps:**
  1. On PO-2026-0002 in Pending, attempt Pending→Completed. → Refused naming the illegal transition.
  2. Complete PO-2026-0001 (with output); attempt any transition. → Refused (terminal).
  3. Attempt Interrupted→Completed on an interrupted fixture order. → Refused.
- **Pass/fail:** all illegal transitions refused; legal ones (per URS-W1-002) allowed.

### TC-W1-003 — `state_history` audit with mandatory reasons *(Integration)*
- **Objective:** audit rows and reason enforcement. **URS:** URS-W1-003.
- **Steps:**
  1. Transition PO-2026-0001 Pending→Accepted (P. Krüger) →In Progress (O. Weber). → Two `state_history` rows, correct users, ascending timestamps.
  2. Decline PO-2026-0002 without a reason. → Refused. With reason "Kunde storniert". → Succeeds; reason stored.
- **Pass/fail:** rows/users/reasons exactly as expected.

### TC-W1-004 — Anchor reconciliation: accept requires submit; shortfall completion *(Integration)*
- **Objective:** exec_state ↔ anchor hooks. **URS:** URS-W1-004.
- **Steps:**
  1. With anchor Work Order in Draft, attempt acceptance of PO-2026-0001. → Refused until submitted.
  2. In Progress with 480 kg of 500 kg recorded, attempt completion without shortfall reason. → Refused.
  3. Complete with reason "Ausschuss Mischvorgang". → Succeeds; reason in `state_history`.
- **Pass/fail:** all three behaviours exact.

### TC-W1-005 — No unqualified "status" *(Integration)*
- **Objective:** vocabulary rule. **URS:** URS-W1-004 (AC-3).
- **Steps:**
  1. Scan `rheinwerk_mes` field/label catalogue for unqualified "status" on canonical DocTypes/screens. → Zero occurrences (`exec_state`/`qa_state`/`gov_state` only).
- **Pass/fail:** zero occurrences.

### TC-W1-006 — Acceptance gate: dates/line/recipe *(Integration + Design-conformance)*
- **Objective:** accept gate parity and refusal presentation. **URS:** URS-W1-005.
- **Steps:**
  1. Attempt acceptance of PO-2026-0002 without `production_line`. → Modal refusal naming rule, record PO-2026-0002, missing field, resolution; logged; not a toast.
  2. Set start 15.03.2026 / end 14.03.2026; retry. → Refused citing date range.
  3. Fix dates (10.03.2026–12.03.2026), set LINE-1 and Accepted recipe; retry. → Accepted.
- **Pass/fail:** refusals and success exactly as specified; refusal is modal and logged.

### TC-W1-007 — Recipe-Accepted gate *(Integration)*
- **Objective:** orders reference only Accepted recipes. **URS:** URS-W1-006.
- **Steps:**
  1. With BOM-RW-CHM-0003-001 governance in Draft, attempt acceptance of PO-2026-0002. → Refused naming recipe + `gov_state`.
  2. Progress recipe to Accepted; retry. → Succeeds.
- **Pass/fail:** both as expected.

### TC-W1-008 — Completion gate: output > 0 *(Integration)*
- **Objective:** completion gate parity. **URS:** URS-W1-007.
- **Steps:**
  1. PO-2026-0001 In Progress, recorded output 0 kg; attempt completion. → Modal refusal citing zero output.
  2. Record 500 kg via job cards; retry. → Completed.
- **Pass/fail:** both as expected.

### TC-W1-009 — Material-availability gate at start *(Integration)*
- **Objective:** hard availability gate. **URS:** URS-W1-008.
- **Steps:**
  1. RM Lager Nord holds 400 kg available RW-CHM-0001; attempt start of PO-2026-0001 (needs 500 kg). → Refused listing RW-CHM-0001 shortfall 100 kg.
  2. Receive BATCH-A-0001 (500 kg); retry. → Starts.
  3. Reserve 200 kg via another order's draft document; verify availability calculation excludes it.
- **Pass/fail:** shortfall list exact; reserved stock excluded.

### TC-W1-010 — Reservations cleared on decline/abandon *(Integration)*
- **Objective:** listener parity. **URS:** URS-W1-009.
- **Steps:**
  1. PO-2026-0002 holds an active 50 kg RW-CHM-0002 reservation; decline with reason. → SRE cancelled; 50 kg back in available quantity.
- **Pass/fail:** reservation released exactly.

### TC-W1-011 — Over-production hard stop *(Integration)*
- **Objective:** anchor error kept. **URS:** URS-W1-010.
- **Steps:**
  1. PO-2026-0001 for 500 kg, allowance 0 %; record manufacture 510 kg. → Refused with over-production error; zero SLEs written.
- **Pass/fail:** refusal and no ledger writes.

### TC-W1-012 — Stopped-order freeze *(Integration)*
- **Objective:** anchor freeze kept. **URS:** URS-W1-011.
- **Steps:**
  1. Stop PO-2026-0001's anchor Work Order; submit MIX job card. → Refused citing stopped order.
- **Pass/fail:** refusal exact.

### TC-W1-013 — Closed order terminal *(Integration)*
- **Objective:** anchor rule kept. **URS:** URS-W1-012.
- **Steps:**
  1. Close PO-2026-0002's anchor Work Order; attempt stop and re-open. → Both refused.
- **Pass/fail:** both refusals.

### TC-W1-014 — Expired-batch consumption and picking stops *(Integration + Design-conformance)*
- **Objective:** expiry hard stop per policy. **URS:** URS-W1-013.
- **Preconditions:** BATCH-A-0002 expiry 30.06.2026; system date 01.07.2026.
- **Steps:**
  1. W. Braun issues 5 kg from BATCH-A-0002. → Modal refusal naming BATCH-A-0002, expiry 30.06.2026, resolution options; no SLE.
  2. Save a pick list including BATCH-A-0002. → Refused listing the expired batch.
- **Pass/fail:** both refusals; date rendered DD.MM.YYYY.

### TC-W1-015 — `gov_state` workflow transitions *(Integration)*
- **Objective:** 5-state recipe lifecycle. **URS:** URS-W1-014.
- **Steps:**
  1. T. Schmid creates governance for BOM-RW-CHM-0003-001 + RT-COMPOUND-01. → Draft.
  2. Draft→Checked→Draft→Checked→Accepted. → All succeed in order.
  3. Attempt Accepted→Draft and Accepted→Checked. → Refused.
  4. On a second fixture recipe in Checked, decline. → Declined (terminal).
- **Pass/fail:** transition set exactly as URS-W1-014.

### TC-W1-016 — Structural validators at acceptance *(Integration)*
- **Objective:** validator battery. **URS:** URS-W1-015.
- **Steps:**
  1. Break RW-CHM-0002 line UoM (no conversion); attempt acceptance. → Refused naming UoM validator + line.
  2. Attempt acceptance of a component-less fixture BOM. → Refused naming completeness validator.
  3. Correct BOM-RW-CHM-0003-001; accept. → Succeeds; validator results stored on the record.
- **Pass/fail:** named validator failures and clean pass.

### TC-W1-017 — Accepted immutability and Outdated versioning *(Integration)*
- **Objective:** change control. **URS:** URS-W1-016.
- **Steps:**
  1. Edit component lines of Accepted BOM-RW-CHM-0003-001. → Refused citing immutability.
  2. Create successor BOM version; accept its governance. → Predecessor `gov_state` = Outdated automatically.
- **Pass/fail:** both exact.

### TC-W1-018 — In-use lock *(Integration)*
- **Objective:** active orders lock recipes. **URS:** URS-W1-017.
- **Steps:**
  1. PO-2026-0001 In Progress on BOM-RW-CHM-0003-001; attempt outdate. → Refused naming PO-2026-0001.
  2. Complete PO-2026-0001; retry with accepted successor. → Succeeds.
- **Pass/fail:** refusal then success.

### TC-W1-019 — Handling Unit as reference layer *(Integration)*
- **Objective:** HU never a parallel quantity store. **URS:** URS-W1-018.
- **Steps:**
  1. W. Braun creates HU-000123 ("Palette", NORD-A-01-01) containing 500 kg RW-CHM-0001 / BATCH-A-0001. → Saves with content row.
  2. Compare HU content sum vs anchor ledger qty for BATCH-A-0001 in RM Lager Nord. → Ledger is truth; HU holds references; divergence raises a reconciliation flag, not a second quantity.
- **Pass/fail:** both checks pass.

### TC-W1-020 — Storage Location warehouse scoping *(Integration)*
- **Objective:** location tree scoped per warehouse. **URS:** URS-W1-019.
- **Steps:**
  1. Create NORD-A-01-01 under RM Lager Nord; assign to HU-000123. → Succeeds.
  2. Offer NORD-A-01-01 for an HU in FG Lager Süd. → Not selectable.
- **Pass/fail:** scoping enforced.

### TC-W1-021 — Per-warehouse disposal algorithms *(Integration)*
- **Objective:** FEFO/FIFO per warehouse. **URS:** URS-W1-020.
- **Steps:**
  1. RM Lager Nord (FEFO) holds BATCH-A-0001 (31.12.2026) + BATCH-A-0002 (30.06.2026, unexpired fixture date); auto-allocate 20 kg. → BATCH-A-0002 selected first.
  2. FG Lager Süd (FIFO) holds BATCH-C-1001 (older) + BATCH-C-1002; auto-allocate. → BATCH-C-1001 first.
- **Pass/fail:** both selections exact.

### TC-W1-022 — Batch-aware Stock Entries with purpose mapping *(Integration)*
- **Objective:** one ledger, mapped purposes. **URS:** URS-W1-021.
- **Steps:**
  1. Book receipt 500 kg RW-CHM-0001 as BATCH-A-0001 into RM Lager Nord / NORD-A-01-01 / HU-000123. → Material Receipt Stock Entry posts; ledger 500 kg with batch allocation.
  2. Issue 100 kg BATCH-A-0001. → Material Issue posts; ledger 400 kg.
- **Pass/fail:** postings and quantities exact.

### TC-W1-023 — Legacy bridge affordance *(Design-conformance)*
- **Objective:** old names on hover; flag removable. **URS:** URS-W1-022.
- **Steps:**
  1. Hover the recipe field on PO-2026-0001. → Shows "was: Technology".
  2. Disable the feature flag; hover again. → No legacy name.
- **Pass/fail:** both as expected.

### TC-W1-024 — Draft makes reservation *(Integration)*
- **Objective:** Qcadoo semantics on SRE. **URS:** URS-W1-023.
- **Steps:**
  1. With 500 kg BATCH-A-0001 available, save a draft issue for 200 kg RW-CHM-0001. → SRE flagged `draft_reservation` for 200 kg; available 300 kg; on-hand 500 kg.
- **Pass/fail:** all three quantities exact.

### TC-W1-025 — Draft deletion releases reservation *(Integration)*
- **Objective:** release semantics. **URS:** URS-W1-024.
- **Steps:**
  1. Delete the draft from TC-W1-024. → SRE cancelled; available back to 500 kg.
- **Pass/fail:** exact restoration.

### TC-W1-026 — Order-level SRE auto-reserve *(Integration)*
- **Objective:** anchor-native order reservations. **URS:** URS-W1-025.
- **Steps:**
  1. Accept PO-2026-0001 with auto-reserve on. → SREs reserving 500 kg component stock exist, visible from the order.
- **Pass/fail:** SREs present and linked.

### TC-W1-027 — Operator job-card execution *(Journey)*
- **Objective:** job cards, time logs, output. **URS:** URS-W1-026.
- **Steps:**
  1. PO-2026-0001 In Progress; O. Weber opens shop-floor view. → Job cards for MIX (LINE-1/MIX-01) and FILL (LINE-1/FILL-01) listed.
  2. Start/stop work on MIX. → Time log with start/end and duration.
  3. Record 500 kg on FILL; submit. → Order recorded output = 500 kg.
- **Pass/fail:** all three steps exact; Terminal Card layout (one task, giant primary action, order/operation in header).

### TC-W1-028 — Pause/resume with log split *(Journey)*
- **Objective:** On Hold semantics. **URS:** URS-W1-027.
- **Steps:**
  1. Pause the MIX job card mid-work. → On Hold; open time log closed.
  2. Resume. → New time log; Work In Progress.
  3. Pause again; attempt submit. → Refused (on hold / completeness rule).
- **Pass/fail:** all as expected.

### TC-W1-029 — Scanner-first identification *(Design-conformance)*
- **Objective:** always-focused scan field with confirmation. **URS:** URS-W1-028.
- **Steps:**
  1. On the terminal, scan PO-2026-0001 barcode. → Job queue loads, no pointer used.
  2. Scan BATCH-A-0001 on the material-issue step. → Full-row highlight + audible confirmation.
  3. Scan unknown code "XX-0000". → Inline error naming the code; scan field still focused.
- **Pass/fail:** all three behaviours exact.

### TC-W1-030 — Characterisation-parity suite vs W1 gates *(Parity)*
- **Objective:** W0 contracts pass against the target implementation. **URS:** URS-W1-002, -005, -007, -015, -020.
- **Steps:**
  1. Run the transition-legality contract (`OrderState.java:54-81`). → Pass.
  2. Run the acceptance-gate contract (`OrderStateValidationService.java:44-47`). → Pass.
  3. Run the completion-gate contract (`OrderStateValidationService.java:54-63`). → Pass.
  4. Run the technology-validator contracts in W1 scope (`TechnologyValidationService.java:91-707`). → Pass.
  5. Run the FEFO contract (`ResourceManagementServiceImpl.java:1015-1027`). → Pass.
- **Pass/fail:** every parity contract green (expiry contract excluded — see §4).

### TC-W1-031 — Per-transition role gating *(NFR/Integration)*
- **Objective:** workflow-state-level RBAC. **URS:** URS-W1-029.
- **Steps:**
  1. O. Weber (operator only) attempts Pending→Accepted on PO-2026-0002. → Permission refusal; no state change; refusal audited.
  2. P. Krüger performs the same transition. → Succeeds.
  3. W. Braun attempts Checked→Accepted on a recipe. → Refused.
- **Pass/fail:** all three exact with audit rows.

### TC-W1-032 — Expiry policy: hard stop in FEFO allocation *(Integration)*
- **Objective:** target expiry behaviour. **URS:** URS-W1-030 (AC-1).
- **Preconditions:** system date 01.07.2026; BATCH-A-0002 expired 30.06.2026 in RM Lager Nord (FEFO).
- **Steps:**
  1. Auto-allocate Additiv K7 demand covered by unexpired stock. → BATCH-A-0002 skipped.
  2. Auto-allocate demand only coverable by BATCH-A-0002. → Issue refused; never silently issued; expiring/expired stock flagged amber/red.
- **Pass/fail:** both exact.

### TC-W1-033 — Expiry divergence recorded with sign-off *(Parity)*
- **Objective:** deviation is explicit and signed off. **URS:** URS-W1-030 (AC-2/AC-3).
- **Steps:**
  1. Run the legacy Plant A expiry characterisation contract (FEFO-advisory: expired resource issuable) against the target. → Delta reported as *intentional divergence* linked to the sign-off reference, not a parity failure.
  2. Run the W1 exit verification with the sign-off identifier removed from the decision record. → Verification fails.
  3. Restore sign-off (name/role/date); re-run. → Passes.
- **Pass/fail:** divergence classification and sign-off gate both work.

### TC-W1-034 — Per-gate behaviour record generation *(Integration)*
- **Objective:** W1-10 record generated from harness results. **URS:** URS-W1-031.
- **Steps:**
  1. Generate the record after a full harness run. → One row per W1 gate (acceptance, recipe-Accepted, completion, material availability, transition legality, over-production, stopped freeze, closed terminal, expiry, in-use lock) with verdict + legacy citation.
  2. Check the expiry row. → Verdict Divergence, links URS-W1-030 sign-off; all other rows Parity.
  3. Break one contract without recording a divergence; regenerate. → Generation fails.
- **Pass/fail:** all three exact.

### TC-W1-035 — Latency under load *(NFR)*
- **Objective:** scan/gate latency budget. **URS:** URS-W1-032.
- **Steps:**
  1. Run 100 sequential scans of BATCH-A-0001 on the terminal profile; measure. → p95 server-confirmed ≤ 300 ms; UI feedback < 100 ms each.
  2. Delay server 2 s; trigger completion. → Progress shown on the control; no success indication before server confirmation.
- **Pass/fail:** both thresholds met.

### TC-W1-036 — Gated-action audit log *(NFR)*
- **Objective:** refusals and transitions logged immutably. **URS:** URS-W1-033.
- **Steps:**
  1. Trigger the TC-W1-006 refusal; open the order's audit view as B. Vogel. → Refusal row with gate name, missing field, user, timestamp.
  2. Attempt to modify that audit entry via API. → Refused.
- **Pass/fail:** both exact.

### TC-W1-037 — German-first W1 screens *(Design-conformance)*
- **Objective:** i18n on W1 scope. **URS:** URS-W1-034.
- **Steps:**
  1. Locale de; trigger the expiry refusal. → Modal shows 30.06.2026 and kg, from externalized strings.
  2. Scan the W1 string catalogue. → Every user-facing string has a German entry.
- **Pass/fail:** both pass.

### TC-W1-038 — End-to-end planner + operator exit journeys *(Journey)*
- **Objective:** the two W1 exit journeys in one run. **URS:** URS-W1-001, URS-W1-026 (with gates from URS-W1-005…008).
- **Steps:**
  1. P. Krüger creates PO-2026-0001 (500 kg RW-CHM-0003, LINE-1, dates 10.03.–12.03.2026, Accepted recipe); accepts. → Accepted; all gates green.
  2. Starts the order with BATCH-A-0001 available. → In Progress; availability gate passed.
  3. O. Weber runs MIX and FILL job cards with scanner identification, pause/resume once, records 500 kg. → Output recorded.
  4. O. Weber completes the order. → Completed; `state_history` full; B. Vogel sees the completed order and audit trail.
- **Pass/fail:** entire journey passes without manual intervention beyond the scripted persona steps.

### TC-W1-039 — Desk/Terminal mode conformance *(Design-conformance)*
- **Objective:** density modes, pills, keyboard path. **URS:** URS-W1-035.
- **Steps:**
  1. Render the job-card screen in Terminal mode; measure. → Base ≥16px; targets ≥48px; same fields as Desk mode.
  2. Render `exec_state`/`gov_state` pills in grayscale. → Distinguishable by icon+label.
  3. Press `?` on each W1 screen. → Shortcut sheet opens; Enter/Esc/arrow paths work end-to-end on the queue.
- **Pass/fail:** all three checks on every W1 screen.

## 4. Parity test section (Absorb scope)

Side-by-side assertions of target behaviour against the Qcadoo characterisation baseline (contracts built in W0, URS-W0-012):

| # | Behaviour | Legacy baseline (contract source) | Target assertion | Verdict | TC |
|---|---|---|---|---|---|
| P-1 | Order transition legality (7-state `canChangeTo`) | `OrderState.java:31-81` | Identical legal/illegal transition set on `exec_state` | Parity | TC-W1-002, TC-W1-030 |
| P-2 | Acceptance requires dates + line + technology/recipe | `OrderStateValidationService.java:44-47` | Same refusal conditions on Pending→Accepted | Parity | TC-W1-006, TC-W1-030 |
| P-3 | Completion blocked at zero recorded output | `OrderStateValidationService.java:54-63` | Same refusal on In Progress→Completed | Parity | TC-W1-008, TC-W1-030 |
| P-4 | Material availability checked at order start; reservations cleared on decline/abandon | `OrderStatesListenerServicePFTD.java:580`, `:633` | Hard gate at start; SRE cancellation on Declined/Abandoned | Parity | TC-W1-009, TC-W1-010 |
| P-5 | Technology validators (tree completeness, unit match, in-use lock) | `TechnologyValidationService.java:91-707` | Same named-validator refusals at Checked→Accepted | Parity | TC-W1-016, TC-W1-018, TC-W1-030 |
| P-6 | Recipe 5-state lifecycle incl. immutable Accepted → Outdated | `TechnologyState.java:33-66` | Identical `gov_state` transition set | Parity | TC-W1-015, TC-W1-017 |
| P-7 | FIFO/LIFO/FEFO/LEFO outbound pick order | `ResourceManagementServiceImpl.java:1015-1027`; `WarehouseAlgorithm.java:26-27` | Same ordering per warehouse algorithm | Parity | TC-W1-021, TC-W1-030 |
| P-8 | Draft documents reserve stock; deletion releases | `ReservationsService.java:81-247` | `draft_reservation` SREs mirror create/release semantics | Parity | TC-W1-024, TC-W1-025 |
| P-9 | Expired stock issuable under FEFO-advisory | Legacy: no hard stop in `ResourceManagementServiceImpl.java:1015-1027`; target: hard stop per `stock_ledger_entry.py:287-299` | Target **deviates deliberately**: hard stop estate-wide | **Intentional divergence — Business sign-off required (URS-W1-030)** | TC-W1-032, TC-W1-033 |

Anchor-adopt behaviours (over-production, stopped freeze, closed terminal, expired-batch throw) are verified against the ERPNext baseline (`services/status.py:29-47,208-224`; `job_card.py:904-910`; `work_order.py:1131-1132`; `stock_ledger_entry.py:287-299`) by TC-W1-011…014 — these are Adopt, not parity-vs-Qcadoo.

## 5. Wave acceptance checklist

Executable form of the W1 exit criteria (`docs/urs/URS-W1-production-core.md` §6); this checklist closes the W1 Epic.

| Exit ID | Check | Test cases | Result |
|---|---|---|---|
| EXIT-W1-1 | Planner journey passes acceptance (create→accept→start with gates→monitor) | TC-W1-001…010, TC-W1-026, TC-W1-038 | ☐ |
| EXIT-W1-2 | Operator journey passes acceptance (job cards, scanner, pause/resume, output→completion) | TC-W1-027…029, TC-W1-008, TC-W1-038 | ☐ |
| EXIT-W1-3 | Recipe governance live with validators, immutability, in-use lock, order gate | TC-W1-007, TC-W1-015…018 | ☐ |
| EXIT-W1-4 | Warehouse fidelity base live (HU, locations, disposal algorithms, reservations; ledger single truth) | TC-W1-019…026 | ☐ |
| EXIT-W1-5 | Behaviour-choice record generated per gate; expiry divergence signed off | TC-W1-030, TC-W1-032…034 | ☐ |
| EXIT-W1-6 | Role model, audit, latency, i18n, Desk/Terminal conformance verified | TC-W1-031, TC-W1-035…037, TC-W1-039 | ☐ |
