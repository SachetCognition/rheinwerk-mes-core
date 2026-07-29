# TST W3 — Planning & Boundary — Test & Verification

**Programme:** Rheinwerk Chemie GmbH MES consolidation — Test & Verification specification, Wave W3
**Verifies:** `docs/20-requirements/planning-boundary/URS-W3-planning-boundary.md` (URS-W3-001…023)
**Test case count:** 27 (TC-W3-001…TC-W3-027).

---

## 1. Test strategy

**Test levels** (unit tests assumed per component and not enumerated here):

- **Integration** — Production Plan ↔ recipe governance ↔ ledger netting ↔ order generation; schedule layer ↔ anchor slot search; ERP interface ↔ message queue ↔ audit; OPC-UA adapter ↔ tracking records.
- **Journey / acceptance** — the end-to-end planning journey (EXIT-W3-1) executed as the planner persona; dispatch hazmat journey as warehouse clerk.
- **Characterization-parity** — target behaviour asserted against the Qcadoo characterization baseline recorded by the W0-6 harness (schedule transitions, TJ/TPZ realization times); parity cases cite the legacy code path being matched (see §4).
- **Migration reconciliation** — not applicable in W3 (no migrated data; see URS-W3 §5). Contract-fixture validation replaces it at the boundary.
- **NFR / Design-conformance** — measured performance, audit sampling, i18n lint, permission matrix, and design-skill conformance checks (Desk/Terminal modes, status pills, gate-refusal presentation, scanner path).

**Environments:** (1) CI environment running contract-fixture and parity suites on every merge; (2) staging with the W1/W2 feature set deployed, a simulated group-ERP endpoint (fixture player), and an OPC-UA simulation server publishing the LINE-1 tag set; (3) a Terminal-mode dispatch station profile for design-conformance cases.

**Test data strategy:** the shared programme fixtures are the single test dataset — products RW-CHM-0001 "Rheinol 40 Basisharz" (25 kg sack), RW-CHM-0002 "Additiv K7" (5 kg pail), RW-CHM-0003 "Rheinol 40 Compound"; raw batches BATCH-A-0001 (500 kg, expiry 31.12.2026), BATCH-A-0002 (50 kg, expiry 30.06.2026, Blocked where stated); FG batches BATCH-C-1001/1002; orders PO-2026-0001 (500 kg RW-CHM-0003 on LINE-1), PO-2026-0002; work centres LINE-1/MIX-01, LINE-1/FILL-01; warehouses RM Lager Nord (FEFO), FG Lager Süd (FIFO); storage location NORD-A-01-01; handling unit HU-000123; BOM-RW-CHM-0003-001 with routing RT-COMPOUND-01; QI template QIT-COMPOUND; personas P. Krüger (planner), O. Weber (operator), Q. Fischer (quality inspector), W. Braun (warehouse clerk), T. Schmid (technologist), B. Vogel (business viewer). ERP fixture set ERP-IN/OUT/GL per URS-W3-013 (external order reference GRP-SO-77001).

## 2. Traceability matrix

Every URS-W3 requirement maps to ≥ 1 test case and every TC maps back — no orphans in either direction.

| URS ID | Test cases | | TC ID | URS ID(s) |
|---|---|---|---|---|
| URS-W3-001 | TC-W3-001 | | TC-W3-001 | URS-W3-001 |
| URS-W3-002 | TC-W3-002, TC-W3-003 | | TC-W3-002 | URS-W3-002 |
| URS-W3-003 | TC-W3-004 | | TC-W3-003 | URS-W3-002 |
| URS-W3-004 | TC-W3-005 | | TC-W3-004 | URS-W3-003 |
| URS-W3-005 | TC-W3-006, TC-W3-007 | | TC-W3-005 | URS-W3-004 |
| URS-W3-006 | TC-W3-008, TC-W3-009 | | TC-W3-006 | URS-W3-005 |
| URS-W3-007 | TC-W3-010 | | TC-W3-007 | URS-W3-005 |
| URS-W3-008 | TC-W3-011 | | TC-W3-008 | URS-W3-006 |
| URS-W3-009 | TC-W3-012 | | TC-W3-009 | URS-W3-006 |
| URS-W3-010 | TC-W3-013 | | TC-W3-010 | URS-W3-007 |
| URS-W3-011 | TC-W3-014 | | TC-W3-011 | URS-W3-008 |
| URS-W3-012 | TC-W3-015 | | TC-W3-012 | URS-W3-009 |
| URS-W3-013 | TC-W3-016 | | TC-W3-013 | URS-W3-010 |
| URS-W3-014 | TC-W3-017 | | TC-W3-014 | URS-W3-011 |
| URS-W3-015 | TC-W3-018 | | TC-W3-015 | URS-W3-012 |
| URS-W3-016 | TC-W3-019 | | TC-W3-016 | URS-W3-013 |
| URS-W3-017 | TC-W3-020 | | TC-W3-017 | URS-W3-014 |
| URS-W3-018 | TC-W3-021, TC-W3-022 | | TC-W3-018 | URS-W3-015 |
| URS-W3-019 | TC-W3-023 | | TC-W3-019 | URS-W3-016 |
| URS-W3-020 | TC-W3-024 | | TC-W3-020 | URS-W3-017 |
| URS-W3-021 | TC-W3-025 | | TC-W3-021 | URS-W3-018 |
| URS-W3-022 | TC-W3-026 | | TC-W3-022 | URS-W3-018 |
| URS-W3-023 | TC-W3-027 | | TC-W3-023 | URS-W3-019 |
| — | — | | TC-W3-024 | URS-W3-020 |
| — | — | | TC-W3-025 | URS-W3-021 |
| — | — | | TC-W3-026 | URS-W3-022 |
| — | — | | TC-W3-027 | URS-W3-023 |

## 3. Test cases

Each case: objective, linked URS, preconditions & fixtures, numbered steps with expected result per step, pass/fail rule, type tag.

### TC-W3-001 — Create Production Plan from sales input [Journey]
**Objective:** Verify Production Plan creation from a sales input. **URS:** URS-W3-001.
**Preconditions:** Sales input for 500 kg RW-CHM-0003 → FG Lager Süd exists; user P. Krüger (planner role).
1. P. Krüger opens Planning work queue and creates a Production Plan from the sales input. → Plan drafted with one row: RW-CHM-0003, 500 kg, FG Lager Süd.
2. Submit the plan. → Plan submitted, non-editable, visible in the planning work queue.
3. Verify the plan detail renders in Desk mode with kg suffix and DD.MM.YYYY dates. → Conforms.
**Pass/fail:** all three expected results exact; any deviation in item/qty/warehouse fails.

### TC-W3-002 — BOM explosion quantities [Integration]
**Objective:** Verify explosion math through Accepted BOM incl. sub-assembly. **URS:** URS-W3-002.
**Preconditions:** BOM-RW-CHM-0003-001 Accepted (`gov_state`), 20 kg RW-CHM-0001 + 1 kg RW-CHM-0002 per 25 kg output; plan from TC-W3-001.
1. Explode the plan. → Component requirements computed.
2. Read computed requirements. → Exactly 400 kg RW-CHM-0001 and 20 kg RW-CHM-0002.
**Pass/fail:** quantities exact to 3 decimals; anything else fails.

### TC-W3-003 — Non-Accepted recipe refused with gate-refusal presentation [Design-conformance]
**Objective:** Verify Draft-recipe planning refusal names rule/record/resolution modally. **URS:** URS-W3-002 (AC-2).
**Preconditions:** A Draft-`gov_state` BOM for RW-CHM-0003 exists.
1. P. Krüger attempts to plan RW-CHM-0003 selecting the Draft BOM. → Refusal is modal (not a toast), names the rule (only Accepted recipes plannable), the record (Draft BOM id), and the resolution.
2. Check the audit log. → Refusal logged.
**Pass/fail:** all four properties (modal, rule, record, resolution) + log entry present; missing any one fails.

### TC-W3-004 — MRP netting vs ledger, reservations and Blocked stock [Integration]
**Objective:** Verify netting counts only available ledger stock. **URS:** URS-W3-003.
**Preconditions:** BATCH-A-0001 500 kg Released in RM Lager Nord; BATCH-A-0002 50 kg `qa_state` Blocked; requirements from TC-W3-002.
1. Run netting. → No Material Request for RW-CHM-0001 (500 ≥ 400).
2. Inspect RW-CHM-0002 result. → Material Request for 20 kg RW-CHM-0002 generated (Blocked stock not counted).
**Pass/fail:** both outcomes exact; counting Blocked stock as available fails.

### TC-W3-005 — Order generation in exec_state Pending [Integration]
**Objective:** Verify plan→order generation with state layer and pill rendering. **URS:** URS-W3-004.
**Preconditions:** Plan from TC-W3-001 submitted.
1. Generate orders. → PO-2026-0001 exists: 500 kg RW-CHM-0003, LINE-1, `exec_state` Pending; `state_history` has creator + timestamp.
2. View the order row in the queue. → State shown as status pill (icon + label + colour), label exactly "Pending", id PO-2026-0001 in mono.
**Pass/fail:** state value, history entry, and pill composition all exact.

### TC-W3-006 — Line schedule lifecycle Draft→Approved/Rejected [Journey]
**Objective:** Verify schedule creation and approval/rejection. **URS:** URS-W3-005.
**Preconditions:** PO-2026-0001 and PO-2026-0002 in `exec_state` Accepted on LINE-1.
1. P. Krüger creates a LINE-1 schedule. → State Draft; both orders with computed start/end.
2. Approve. → State Approved; schedule is the operative LINE-1 sequence.
3. Create a second Draft schedule and reject it. → State Rejected; no operative effect.
**Pass/fail:** the three state outcomes exact.

### TC-W3-007 — Schedule state-transition parity vs ScheduleState.java [Parity]
**Objective:** Assert target schedule transitions equal the legacy set. **URS:** URS-W3-005 (AC-3). Legacy path: `Chem_mes` `orders/states/constants/ScheduleState.java:8-24`.
**Preconditions:** W0-6 characterization baseline for ScheduleState loaded.
1. Enumerate target's allowed schedule transitions programmatically. → Exactly {Draft→Approved, Draft→Rejected}.
2. Attempt Approved→Draft and Rejected→Approved. → Both refused.
**Pass/fail:** transition set equality; any extra or missing transition fails.

### TC-W3-008 — TJ/TPZ realization-time computation [Integration]
**Objective:** Verify realization times from TJ/TPZ norms. **URS:** URS-W3-006.
**Preconditions:** RT-COMPOUND-01: MIX @ LINE-1/MIX-01 TPZ 30 min, TJ 0.6 min/kg; FILL @ LINE-1/FILL-01 TPZ 15 min, TJ 0.3 min/kg; PO-2026-0001 = 500 kg.
1. Compute realization time. → MIX = 330 min; FILL = 165 min; order total 495 min (sequential).
**Pass/fail:** all three values exact to the minute.

### TC-W3-009 — Realization-time parity vs OrderRealizationTimeServiceImpl [Parity]
**Objective:** Assert target realization times match the legacy characterization baseline. **URS:** URS-W3-006 (AC-2). Legacy path: `Chem_mes` `productionScheduling/OrderRealizationTimeServiceImpl.java`.
**Preconditions:** W0-6 fixture matrix (≥ 10 TJ/TPZ input combinations incl. edge values qty=1, TPZ=0) with recorded legacy outputs.
1. Run the fixture matrix against the target calculator. → Every output equals the legacy value exactly (to the minute).
**Pass/fail:** 100% match; a single mismatch fails.

### TC-W3-010 — Changeover norms applied in sequencing [Integration]
**Objective:** Verify changeover time insertion. **URS:** URS-W3-007.
**Preconditions:** 45-min changeover norm on LINE-1 for RW-CHM-0003→other; approved schedule with PO-2026-0001 then PO-2026-0002.
1. Read PO-2026-0002's computed start. → ≥ PO-2026-0001 end + 45 min.
2. Remove the norm, resequence two orders without a norm. → No changeover inserted; transition annotated "no changeover norm".
**Pass/fail:** both outcomes exact.

### TC-W3-011 — Capacity refusal names work centre and resolution [Integration]
**Objective:** Verify anchor slot-search refusal presentation. **URS:** URS-W3-008.
**Preconditions:** Capacity planning on; LINE-1/MIX-01 `production_capacity` = 1 fully booked by PO-2026-0001 in the window.
1. Schedule PO-2026-0002's MIX operation in the same window. → Capacity refusal: modal + logged, naming LINE-1/MIX-01, the blocking booking, and earliest feasible slot.
**Pass/fail:** refusal raised with all three named elements; a toast-only error fails.

### TC-W3-012 — No-optimiser scope audit [NFR]
**Objective:** Confirm deliberate absence of an optimiser and presence of decision record D4. **URS:** URS-W3-009.
1. Audit delivered W3 components against the scope baseline. → No optimiser component present.
2. Check the programme decision register. → D4 entry exists with a status.
**Pass/fail:** both true.

### TC-W3-013 — Orders-in: happy path, duplicate, rejection [Integration]
**Objective:** Verify inbound demand processing incl. idempotency and rejection. **URS:** URS-W3-010.
**Preconditions:** Contract v1.0 fixtures ERP-IN-001 (GRP-SO-77001, 500 kg RW-CHM-0003), ERP-IN-001 duplicate, ERP-IN-002 (unknown item).
1. Play ERP-IN-001. → Sales-input record referencing GRP-SO-77001 created, available to plan creation.
2. Replay ERP-IN-001. → No duplicate demand; duplicate logged with GRP-SO-77001.
3. Play ERP-IN-002. → Rejected to error queue with machine-readable reason; no partial writes.
**Pass/fail:** all three exact; any partial write on rejection fails.

### TC-W3-014 — Confirmations out on Completed, with durable queue [Integration]
**Objective:** Verify confirmation emission and store-and-forward. **URS:** URS-W3-011.
**Preconditions:** PO-2026-0001 In Progress, linked to GRP-SO-77001; simulated ERP endpoint controllable.
1. Complete PO-2026-0001 (500 kg into BATCH-C-1001). → Exactly one confirmation with GRP-SO-77001, RW-CHM-0003, 500 kg, BATCH-C-1001; schema-valid.
2. Take endpoint offline; complete PO-2026-0002; bring endpoint back. → Message queued during outage, delivered once on recovery; backlog visible on health surface during outage.
**Pass/fail:** exactly-once delivery per completion; loss or duplication fails.

### TC-W3-015 — GL postings out with account map and unmapped hold [Integration]
**Objective:** Verify boundary GL emission and unmapped-account handling. **URS:** URS-W3-012.
**Preconditions:** FG Lager Süd mapped to group-ERP accounts; a second warehouse deliberately unmapped; BATCH-C-1001 manufacture at 4.20 €/kg.
1. Post the 500 kg manufacture receipt. → GL message with 2,100.00 € debit/credit pair on mapped accounts; schema-valid.
2. Trigger a posting on the unmapped warehouse. → Posting held in unmapped-accounts queue; alert names warehouse and missing map entry; nothing emitted.
**Pass/fail:** amount exact; emission of an unmapped posting fails.

### TC-W3-016 — Contract fixture suite and versioning in CI [Integration]
**Objective:** Verify the frozen contract's fixture suite and version discipline. **URS:** URS-W3-013.
1. Run the CI contract job. → ≥ 9 fixtures (happy/duplicate/rejection × 3 message types) all pass; run linked from evidence pack.
2. Introduce a non-backward-compatible schema change in a branch. → Contract version increments; v1.0 and v1.1 fixture sets both pass in the transition window.
**Pass/fail:** suite green and versioning enforced.

### TC-W3-017 — Interface health KPI drill-down and audited replay [Journey]
**Objective:** Verify Command Dashboard tile → error queue → replay with audit. **URS:** URS-W3-014.
**Preconditions:** One rejected message from TC-W3-013 step 3.
1. B. Vogel opens the Command Dashboard. → Plain-language tile "ERP messages needing attention: 1" drills into the professional error-queue view showing the rejection reason.
2. P. Krüger corrects and replays the message. → Processing succeeds; audit records who, when, message reference.
**Pass/fail:** drill-down lands on the same-data queue view (not a separate report) and audit entry complete.

### TC-W3-018 — OPC-UA event ingestion and unmatched queue [Integration]
**Objective:** Verify tag events land on the right order/operation and orphans are held. **URS:** URS-W3-015.
**Preconditions:** OPC-UA simulator on LINE-1/MIX-01 tags; PO-2026-0001 In Progress on LINE-1.
1. Publish a produced-count event of 25 kg. → Tracking event of 25 kg on PO-2026-0001/MIX within 5 s, source "OPC-UA".
2. Publish an event for FILL-01 with no order In Progress there. → Event in unmatched-events queue; not dropped.
**Pass/fail:** correct attribution and ≤ 5 s latency; silent drop fails.

### TC-W3-019 — Tag-mapping administration and validation [Integration]
**Objective:** Verify mapping CRUD and invalid-work-centre refusal. **URS:** URS-W3-016.
1. T. Schmid maps `ns=2;s=Line1.Mix01.ProducedKg` → LINE-1/MIX-01 / produced-count. → Saved; events on the tag resolve to LINE-1/MIX-01.
2. Attempt a mapping to non-existent work centre "LINE-9/XX-99". → Save refused naming the invalid code.
**Pass/fail:** both exact; mono rendering of tag ids verified in the admin table.

### TC-W3-020 — Store-and-forward across a 10-minute outage [Integration]
**Objective:** Verify buffering, ordering, and late flags. **URS:** URS-W3-017.
1. Disconnect adapter from MES 10 min; publish 3 produced-count events on MIX-01. → Nothing lost at adapter.
2. Reconnect. → All 3 events recorded on PO-2026-0001 in original order with original equipment timestamps and late-delivery flags.
**Pass/fail:** 3/3 in order with flags; any loss/reorder fails.

### TC-W3-021 — Hazmat dispatch label content [Journey]
**Objective:** Verify ADR label data for a hazmat FG batch. **URS:** URS-W3-018.
**Preconditions:** RW-CHM-0003 hazmat profile UN 1263, "FARBE", class 3, PG III; BATCH-C-1001 in FG Lager Süd.
1. W. Braun (Terminal mode, dispatch station) scans HU/batch and produces label data for BATCH-C-1001. → Label contains UN 1263, "FARBE", class 3, PG III, BATCH-C-1001, net kg.
**Pass/fail:** all label fields exact.

### TC-W3-022 — Incomplete ADR profile blocks dispatch [Design-conformance]
**Objective:** Verify dispatch refusal presentation for missing UN number. **URS:** URS-W3-018 (AC-2).
**Preconditions:** A hazmat item whose profile lacks a UN number, with a batch in stock.
1. Attempt dispatch of the batch. → Modal, logged refusal naming rule (ADR data incomplete), record (item + missing field), resolution (complete profile).
2. Verify in Terminal mode: 48 px targets, scanner field focused. → Conforms.
**Pass/fail:** refusal completeness + Terminal-mode conformance.

### TC-W3-023 — External-sync register completeness and contract coverage [Integration]
**Objective:** Verify the survey register and its coupling to the contract. **URS:** URS-W3-019.
1. Review the published register. → Every entry has system, direction, data objects, evidence-of-use, disposition; §8.2 #6 marked answered.
2. For each "carry" entry, check contract v1.0 fixtures. → A fixture exists per carried sync.
**Pass/fail:** no entry incomplete; no carried sync without a fixture.

### TC-W3-024 — Performance budgets [NFR]
**Objective:** Measure the four URS-W3-020 budgets. **URS:** URS-W3-020.
1. Load a 200-order LINE-1 schedule board. → First meaningful render ≤ 2 s; table virtualized.
2. Time planner actions (approve, resequence). → UI feedback < 100 ms; longer ops show progress on the control.
3. W. Braun scans HU-000123 at dispatch. → Server-confirmed ≤ 300 ms with full-row visual + audible confirmation.
4. Play an orders-in fixture. → End-to-end ≤ 10 s.
**Pass/fail:** all four budgets met in 3 consecutive runs.

### TC-W3-025 — Audit coverage of gated and boundary actions [NFR]
**Objective:** Sample the audit trail across the four W3 audit classes. **URS:** URS-W3-021.
1. Trigger: schedule approval (TC-W3-006), capacity refusal (TC-W3-011), message reject+replay (TC-W3-013/017), OPC-UA event (TC-W3-018). → Each produces an audit record with actor/source, timestamp, action, record reference, outcome.
2. Attempt to modify an audit record. → No update path exists.
**Pass/fail:** 4/4 classes covered and immutability holds.

### TC-W3-026 — German-first i18n and formats [NFR]
**Objective:** Verify locale rendering and string externalization. **URS:** URS-W3-022.
1. Set locale de; open the schedule board with PO-2026-0001 planned start 31.12.2026. → Date "31.12.2026"; quantity "500 kg" German-formatted; pill labels from the externalized glossary.
2. Run the string-extraction lint over W3 screens. → Zero hard-coded translatable strings, zero concatenations.
**Pass/fail:** both checks clean.

### TC-W3-027 — Permission matrix for planning/boundary actions [NFR]
**Objective:** Verify workflow-level access control. **URS:** URS-W3-023.
1. O. Weber attempts schedule approval. → Refused + audited.
2. P. Krüger approves. → Succeeds.
3. P. Krüger (no interface-admin) attempts message replay. → Refused naming required permission.
4. Interface admin replays; technologist edits tag mapping; non-technologist attempt refused. → As specified.
**Pass/fail:** every allow/deny outcome exact per the matrix.

## 4. Parity test section (Absorb scope)

Absorb items in W3 are the finite-capacity layer semantics (W3-2). The legacy characterization baseline (W0-6 harness) is the contract:

| Parity case | Legacy contract (code path) | Target assertion | Deviation? |
|---|---|---|---|
| TC-W3-007 schedule transitions | `Chem_mes` `orders/states/constants/ScheduleState.java:8-24` (DRAFT/APPROVED/REJECTED, transitions from `canChangeTo`) | Transition set identical | None — exact match required |
| TC-W3-009 realization times | `Chem_mes` `productionScheduling/OrderRealizationTimeServiceImpl.java` (TJ/TPZ norm arithmetic) | Outputs identical to the minute over the fixture matrix | None — exact match required |
| Changeover norms (TC-W3-010) | `Chem_mes` plugin `mes-plugins-line-changeover-norms` (norm lookup between product pairs on a line) | Norm applied when defined; annotated absence otherwise | **Deliberate deviation:** target annotates "no changeover norm" transitions for planner visibility (legacy is silent). Presentation-only; no timing difference. **Business sign-off required** — reference W1-10 behaviour-choice register entry for W3-2. |

Boundary (W3-3/W3-4), SCADA (W3-5) and hazmat (W3-6) are Rebuild/white-space — no legacy baseline exists, so no parity cases; their contracts are the frozen interface fixtures (TC-W3-016) and the URS acceptance criteria.

## 5. Wave acceptance checklist

Executable form of the URS-W3 §6 exit criteria; this checklist closes the W3 Epic.

| Exit check | Verified by | Status gate |
|---|---|---|
| EXIT-W3-1 planning journey end-to-end | TC-W3-001…011 all pass in one chained staging run (GRP-SO-77001 → approved LINE-1 schedule) | All green |
| EXIT-W3-2 contract v1.0 frozen + fixtures in CI | TC-W3-013, TC-W3-014, TC-W3-015, TC-W3-016 | All green, CI link in evidence pack |
| EXIT-W3-3 external-sync register dispositioned | TC-W3-023 | Green + §8.2 #6 answered |
| EXIT-W3-4 SCADA path incl. outage replay | TC-W3-018, TC-W3-019, TC-W3-020 | All green |
| EXIT-W3-5 hazmat dispatch demonstrated | TC-W3-021, TC-W3-022 | Both green |
| EXIT-W3-6 NFR evidence | TC-W3-024, TC-W3-025, TC-W3-026, TC-W3-027 | All green, measurements attached |
| EXIT-W3-7 Won't-scope confirmed (no optimiser; D4 recorded) | TC-W3-012 | Green |
