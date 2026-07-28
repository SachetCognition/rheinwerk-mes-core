# TST W4 — Cutover & Decommission — Test & Verification

**Programme:** Rheinwerk Chemie GmbH MES consolidation — Test & Verification specification, Wave W4
**Verifies:** `docs/urs/URS-W4-cutover-decommission.md` (URS-W4-001…014)
**Test case count:** 18 (TC-W4-001…TC-W4-018).

---

## 1. Test strategy

**Test levels** (unit tests assumed for migration tooling components):

- **Migration reconciliation** — the dominant W4 level: record counts, per-warehouse/facility sum equivalence (quantity and value), and field-level spot checks for the Plant A stock decomposition, Plant A genealogy backfill (incl. `arch_*`), and Plant B backfill; each reconciliation report is a pass/fail artefact for the evidence pack.
- **Characterization-parity** — migrated data must reproduce legacy behaviourally relevant facts: FEFO ordering after migration, `qa_state` mapping per CDM-01, `PRUN_*`→`exec_state` mapping per CDM-02 (see §4).
- **Journey / acceptance** — per-plant runbook dry-runs and persona sign-off journeys on staging loaded with real-volume extracts.
- **Integration** — freeze/unfreeze role revocation, archival restore, migration checkpoint/resume, run-ID rollback.
- **NFR / Design-conformance** — migration window timing, audit immutability, permission matrix, trace-boundary marker presentation on the Trace Ribbon.

**Environments:** (1) staging target loaded via the W0-5 tooling from production-volume legacy extracts of Plants A and B; (2) legacy staging clones of Qcadoo (with populated `arch_*` tables) and OFBiz for freeze/restore rehearsal; (3) a network-isolated build environment for the Qcadoo build-chain archive proof; (4) Terminal/Desk stations for sign-off journeys.

**Test data strategy:** shared programme fixtures embedded into the legacy extracts as sentinel records so migration outcomes are deterministic and human-checkable — Plant A: Resource row (RW-CHM-0001, batch "BATCH-A-0001", 500 kg, expiry 31.12.2026, pallet HU-000123, location NORD-A-01-01, 2.10 €/kg, RM Lager Nord, FEFO) and a `blockedForQualityControl` Resource for BATCH-A-0002 (50 kg, expiry 30.06.2026); a TrackingRecord BATCH-C-1001 ← {BATCH-A-0001 400 kg, BATCH-A-0002 20 kg} plus an equivalent record archived into `arch_*`; Plant B: `InventoryItem` (RW-CHM-0002, lotId "B-K7-0009", 50 kg, expiry 30.06.2026), an `InventoryItem` with NULL lotId, and one production run per `PRUN_*` state for RW-CHM-0003. Personas as fixed: P. Krüger, O. Weber, Q. Fischer, W. Braun, T. Schmid, B. Vogel.

## 2. Traceability matrix

| URS ID | Test cases | | TC ID | URS ID(s) |
|---|---|---|---|---|
| URS-W4-001 | TC-W4-001, TC-W4-002 | | TC-W4-001 | URS-W4-001 |
| URS-W4-002 | TC-W4-003 | | TC-W4-002 | URS-W4-001 |
| URS-W4-003 | TC-W4-004 | | TC-W4-003 | URS-W4-002 |
| URS-W4-004 | TC-W4-005 | | TC-W4-004 | URS-W4-003 |
| URS-W4-005 | TC-W4-006, TC-W4-007 | | TC-W4-005 | URS-W4-004 |
| URS-W4-006 | TC-W4-008, TC-W4-009 | | TC-W4-006 | URS-W4-005 |
| URS-W4-007 | TC-W4-010, TC-W4-011 | | TC-W4-007 | URS-W4-005 |
| URS-W4-008 | TC-W4-012 | | TC-W4-008 | URS-W4-006 |
| URS-W4-009 | TC-W4-013 | | TC-W4-009 | URS-W4-006 |
| URS-W4-010 | TC-W4-014 | | TC-W4-010 | URS-W4-007 |
| URS-W4-011 | TC-W4-015 | | TC-W4-011 | URS-W4-007 |
| URS-W4-012 | TC-W4-016 | | TC-W4-012 | URS-W4-008 |
| URS-W4-013 | TC-W4-017 | | TC-W4-013 | URS-W4-009 |
| URS-W4-014 | TC-W4-018 | | TC-W4-014 | URS-W4-010 |
| — | — | | TC-W4-015 | URS-W4-011 |
| — | — | | TC-W4-016 | URS-W4-012 |
| — | — | | TC-W4-017 | URS-W4-013 |
| — | — | | TC-W4-018 | URS-W4-014 |

No orphans in either direction.

## 3. Test cases

### TC-W4-001 — Runbook structural completeness [Journey]
**Objective:** Verify the three runbooks cover all six journeys with complete step anatomy. **URS:** URS-W4-001.
**Preconditions:** Runbooks for Plants A, B, C drafted; §8.2 #7 answered for Plant B.
1. Audit each runbook against the §5.3 journey list. → All six journeys present per plant.
2. Audit every step. → Every step has owner, precondition, verification, abort path — zero incomplete steps.
3. Check the Plant B precondition section. → Contains the answered §8.2 #7 entry with counted open-run/WIP values.
**Pass/fail:** all three checks 100%; one incomplete step fails.

### TC-W4-002 — Plant A runbook dry-run on staging [Journey]
**Objective:** Prove the Plant A runbook executes end-to-end before it is declared final. **URS:** URS-W4-001 (AC-3).
**Preconditions:** Staging loaded with TC-W4-006/008 migration outputs.
1. Execute the Plant A runbook end-to-end on staging. → Every verification step passes, or the runbook is amended and the dry-run repeated until it does.
2. Record the dry-run report. → Attached to the evidence pack draft.
**Pass/fail:** a complete passing dry-run exists; a runbook declared final without one fails.

### TC-W4-003 — Legacy write freeze with query access retained [Integration]
**Objective:** Verify the freeze mechanics per plant. **URS:** URS-W4-002.
**Preconditions:** Legacy staging clones; cutover point declared for Plant A rehearsal.
1. Apply the Plant A freeze (revoke write roles). → O. Weber's attempt to accept an order in Qcadoo is refused; read of the same order succeeds.
2. Check the decommission register. → Freeze date recorded.
3. At end of the rehearsed read-only period, execute archival. → Query access removed; archival date recorded.
**Pass/fail:** write refused + read allowed + both dates registered.

### TC-W4-004 — Archive package restore test [Integration]
**Objective:** Verify each archive is restorable and complete. **URS:** URS-W4-003.
1. Execute the documented restore of the Plant A package into an isolated environment. → Qcadoo starts; the sentinel legacy order (source of PO-2026-0001 fixtures) is queryable read-only.
2. Review all three packages' register entries. → Each lists content checksum, pinned commit SHA (81d6bb5 / ecf2990 / 31e7970), archive date, retention owner.
**Pass/fail:** restore succeeds once per the procedure and register fields complete.

### TC-W4-005 — Qcadoo build-chain archive, network-isolated [Integration]
**Objective:** Prove independence from `nexus.qcadoo.org`. **URS:** URS-W4-004.
1. In a network-isolated environment with only the archived Maven mirror and sources, build Plant A's WAR (or deploy the archived WAR). → Build/deploy succeeds with zero external repository access (verified by network capture).
2. Check W4 planning. → The archive task started independent of W4-1…W4-5 sequencing.
**Pass/fail:** isolated build/deploy success; any external fetch fails.

### TC-W4-006 — Plant A Resource decomposition of sentinel rows [Migration]
**Objective:** Verify field-level decomposition per CDM-03/CDM-01. **URS:** URS-W4-005.
**Preconditions:** Sentinel Resources for BATCH-A-0001 and BATCH-A-0002 in the Plant A extract.
1. Run the stock backfill. → Completes with run ID.
2. Inspect BATCH-A-0001 targets. → Batch BATCH-A-0001 `qa_state` Released, expiry 31.12.2026; Bin/SLE 500 kg in RM Lager Nord at 2.10; HU-000123 contains 500 kg of BATCH-A-0001; Storage Location NORD-A-01-01 assigned.
3. Inspect BATCH-A-0002. → `qa_state` per CDM-01 map (resource flag → Quarantined; genealogy BLOCKED → Blocked); stock excluded from picking availability.
4. Run a picking availability query for RW-CHM-0001 in RM Lager Nord (FEFO). → Batches offered in expiry order (30.06.2026 before 31.12.2026 where Released).
**Pass/fail:** every field exact; wrong `qa_state` mapping or FEFO order fails.

### TC-W4-007 — Plant A stock reconciliation report [Migration]
**Objective:** Verify counts, per-warehouse sum equivalence, and spot checks. **URS:** URS-W4-005 (reconciliation & rollback).
1. Generate the reconciliation report at production volume. → Batch count = distinct legacy (batch, product) pairs; HU count = distinct pallet numbers.
2. Compare per-warehouse sums. → Σ qty and Σ (qty × rate) per warehouse equal legacy Resource sums, exact to 3 decimals.
3. Verify ≥ 50 random Resource rows field-by-field. → Zero mismatches.
4. Inject one deliberate value error into a copy run. → Sum equivalence fails, cutover abort path triggers, rollback by run ID restores the pre-migration state.
**Pass/fail:** steps 1–3 clean; step 4 proves the rollback condition actually fires.

### TC-W4-008 — Genealogy backfill incl. `arch_*` sentinels [Migration]
**Objective:** Verify genealogy links from live and archived TrackingRecords. **URS:** URS-W4-006.
1. Run the genealogy backfill. → Completes with run ID.
2. Open BATCH-C-1001's genealogy. → `genealogy_links` contain consumed BATCH-A-0001 (400 kg) and BATCH-A-0002 (20 kg); Trace Ribbon shows both upstream.
3. Inspect the sentinel that exists only in `arch_*`. → Its links backfilled identically to live records.
4. Inspect an unmatched resource-batch string. → Identity-only Batch created, flagged `genealogy_incomplete`, counted in the report.
**Pass/fail:** all four exact; dropped `arch_*` history fails.

### TC-W4-009 — Genealogy reconciliation: counts and tree spot checks [Migration]
**Objective:** Verify genealogy reconciliation criteria. **URS:** URS-W4-006.
1. Compare link counts. → Target genealogy link count = legacy used-batch link count, reported separately for live and `arch_*`.
2. Spot-check ≥ 25 trees (≥ 5 from `arch_*`) node-by-node against legacy `producedFrom`/`usedToProduce`. → Zero structural mismatches.
3. Present the `genealogy_incomplete` count to Q. Fischer for acceptance. → Recorded acceptance (or rejection triggering investigation).
**Pass/fail:** counts equal, trees match, acceptance recorded.

### TC-W4-010 — Plant B backfill: sentinel items and status mapping [Migration]
**Objective:** Verify OFBiz backfill field mapping and the fixed `PRUN_*` map. **URS:** URS-W4-007.
1. Run the Plant B backfill. → Completes with run ID.
2. Inspect lot B-K7-0009. → Opening SLE 50 kg of RW-CHM-0002 in the mapped warehouse; Batch B-K7-0009 `qa_state` Released, expiry 30.06.2026; `legacy_refs` = (OFBiz, B-K7-0009).
3. Inspect the seven sentinel production runs (one per `PRUN_*` state). → Mapping exactly: CREATED/SCHEDULED→Pending, DOC_PRINTED→Accepted, RUNNING→In Progress, COMPLETED/CLOSED→Completed, CANCELLED→Abandoned; each with `legacy_refs` to the WorkEffort id.
4. Inspect the NULL-lotId item. → Opening SLE without batch allocation; counted in the no-lot bucket.
**Pass/fail:** every mapping exact; any other `PRUN_*`→In Progress mapping fails.

### TC-W4-011 — Plant B reconciliation: sums, counts, 100% open runs [Migration]
**Objective:** Verify Plant B reconciliation criteria and rollback. **URS:** URS-W4-007.
1. Compare opening SLE count to migrated non-zero `InventoryItem` rows; open-order counts per `exec_state` to legacy per mapped `PRUN_*` state. → Equal.
2. Compare Σ qty per (product, warehouse) with legacy QOH per (product, facility). → Exact equality per facility.
3. Verify ≥ 30 sampled items and 100% of open runs field-by-field. → Zero mismatches.
4. Inject a state mis-map in a copy run. → Reconciliation fails; rollback by run ID; Plant B freeze lift path exercised.
**Pass/fail:** steps 1–3 clean; step 4 proves rollback.

### TC-W4-012 — Trace-boundary register and Trace Ribbon marker [Design-conformance]
**Objective:** Verify the Plant B trace boundary is recorded and disclosed. **URS:** URS-W4-008.
**Preconditions:** §8.2 #3 lot-coverage measurement answered.
1. Review the trace-boundary register. → Contains boundary date, measured lot-coverage %, no-lot quantity bucket (from TC-W4-010 step 4).
2. Q. Fischer opens the Trace Ribbon of a migrated Plant B batch with pre-boundary history. → Upstream shows an explicit boundary marker: hard visual break, labelled with the register entry — not an empty tree presented as complete.
3. Print the ribbon and open the batch's CoA/recall view. → Marker identical in all three.
**Pass/fail:** register complete + marker present, labelled, and consistent across views/print.

### TC-W4-013 — Persona sign-off matrix [Journey]
**Objective:** Verify per-plant sign-off completeness. **URS:** URS-W4-009.
1. Compile the Plant A matrix after the operating period. → Dated, named entries: P. Krüger (plan an order), O. Weber (release + execute & record), Q. Fischer (trace a defect batch + quality disposition), W. Braun (stock journeys), T. Schmid (define & approve a recipe), B. Vogel (business views) — 6/6.
2. Simulate a withheld sign-off. → A named defect with owner is logged; no silent "with exceptions" record possible.
3. Repeat for Plants B and C. → 18 entries total across plants.
**Pass/fail:** 18/18 entries or logged blocking defects; a silent exception fails.

### TC-W4-014 — Decommission evidence pack audit [Integration]
**Objective:** Verify pack completeness closes the Epic. **URS:** URS-W4-010.
1. Audit the Plant B pack. → All six artefact classes present (executed runbook + verifications; reconciliation reports; trace-boundary register; sign-offs; freeze/archival dates + checksums; build-chain archive proof), each cross-linked.
2. Remove one artefact in a copy. → Pack cannot be marked complete.
3. With all three packs complete, evaluate M4. → "All personas on target; legacy read-only then archived; evidence pack signed off" evaluates true from pack contents alone.
**Pass/fail:** all three outcomes exact.

### TC-W4-015 — Legacy-bridge flag retirement per plant [Design-conformance]
**Objective:** Verify per-plant flag-off behaviour and layout stability. **URS:** URS-W4-011.
**Preconditions:** Plant A signed off; Plant B not yet.
1. Switch off the Plant A bridge flag. → Hovering the Recipe reference on PO-2026-0001 as a Plant A user shows no "was: Technology → now: Recipe"; Plant B users still see bridge labels.
2. Compare screenshots before/after flag change. → No layout shift.
**Pass/fail:** both exact.

### TC-W4-016 — Migration window timing and checkpoint resume [NFR]
**Objective:** Verify window fit and resumability. **URS:** URS-W4-012.
1. Time the Plant A staging dry-run at production volume. → Duration ≤ runbook window with ≥ 20% headroom.
2. Interrupt a run mid-warehouse; resume. → Continues from last checkpoint; reconciliation report byte-identical to an uninterrupted run.
3. Verify all writes carry the migration run ID. → Confirmed by sampling.
**Pass/fail:** all three; a resume producing different reconciliation output fails.

### TC-W4-017 — Migration/decommission audit immutability [NFR]
**Objective:** Verify audit records for runs and freeze actions. **URS:** URS-W4-013.
1. Query the Plant B run by run ID. → Operator, source extract checksums, start/end, record counts, reconciliation outcome present.
2. Attempt to update the entry. → No update path exists.
3. Query the TC-W4-003 freeze. → Actor, plant A, timestamp, revoked scope present.
**Pass/fail:** all fields present and immutability holds.

### TC-W4-018 — Migration-operator permission matrix [NFR]
**Objective:** Verify dedicated migration permissions. **URS:** URS-W4-014.
1. P. Krüger attempts a migration rollback. → Refused + audited.
2. The designated migration operator triggers it. → Succeeds with TC-W4-017-conformant audit.
3. Repeat for freeze/unfreeze and archival with each of the six business personas. → All refused; only the migration operator succeeds.
**Pass/fail:** every allow/deny exact.

## 4. Parity test section (Absorb scope)

W4's Absorb scope is *migration* parity: the migrated data must reproduce legacy behavioural facts on the target. The legacy characterization baseline (W0-6) is the contract:

| Parity case | Legacy contract (code path) | Target assertion | Deviation? |
|---|---|---|---|
| TC-W4-006 step 4 FEFO order after migration | `Chem_mes` `materialFlowResources/constants/WarehouseAlgorithm.java:26-27` + `ResourceManagementServiceImpl.java:1015-1027` (FEFO = expiry ascending) | Post-migration picking offers batches in identical expiry order for RM Lager Nord | None — exact match. (Any estate-wide expiry *hard-stop* deviation was decided in W1-9 with its own sign-off; W4 only preserves ordering.) |
| TC-W4-006 steps 2–3 `qa_state` mapping | `Chem_mes` `advancedGenealogy/states/constants/BatchState.java:31-44` (TRACKED⇄BLOCKED) + `ResourceFields.java:84-86` (`blockedForQualityControl`) | TRACKED→Released, BLOCKED→Blocked, resource flag→Quarantined, exactly per CDM-01 | **Deliberate deviation:** legacy has two parallel truth stores; target collapses to one `qa_state`. Mapping table is the contract (ADR-003). **Business sign-off required** — assumption A6 (dual model refers to same physical lots) must be confirmed at sign-off. |
| TC-W4-008 genealogy trees | `Chem_mes` `TrackingRecordFields.java:31-49`; tree browse `AdvancedGenealogyTreeViewListeners.java:71-73`; archive machinery `mes_db_en.sql:292-648` | Node-identical trees for live and `arch_*` records | None — exact match required |
| TC-W4-010 step 3 status map | `VM_ofbiz-framework` `WorkEffortSeedData.xml:160-177` (`PRUN_*` states + `StatusValidChange`) | Fixed CDM-02 map, no other value → In Progress | **Deliberate deviation:** `PRUN_CLOSED` and `PRUN_COMPLETED` both → Completed (target has no separate Closed for migrated history). Recorded in ADR-004 consequences. **Business sign-off required** at Plant B cutover readiness. |
| TC-W4-010 step 2 `qa_state` default | `VM_ofbiz-framework` `product-entitymodel.xml:2419-2427` (`Lot` has no status field) | All OFBiz lots → Released with trace boundary noted | **Deliberate deviation** (no legacy state exists to carry): per CDM-01 "∅ (default Released; trace-boundary noted)". Sign-off is the trace-boundary register acceptance (TC-W4-012). |

## 5. Wave acceptance checklist

Executable form of the URS-W4 §6 exit criteria; this checklist closes the W4 Epic.

| Exit check | Verified by | Status gate |
|---|---|---|
| EXIT-W4-1 runbooks executed, §8.2 #2/#3/#7 answered first | TC-W4-001, TC-W4-002 (and production executions recorded in packs) | All green |
| EXIT-W4-2 18/18 persona sign-offs, no silent exceptions | TC-W4-013 | Green |
| EXIT-W4-3 all reconciliations pass | TC-W4-006, TC-W4-007, TC-W4-008, TC-W4-009, TC-W4-010, TC-W4-011, TC-W4-016 | All green, reports in packs |
| EXIT-W4-4 trace-boundary register published + surfaced | TC-W4-012 | Green |
| EXIT-W4-5 freeze → archive proven, restore tested, build chain isolated | TC-W4-003, TC-W4-004, TC-W4-005 | All green |
| EXIT-W4-6 evidence packs complete, M4 true from contents | TC-W4-014, TC-W4-017 (+ TC-W4-015, TC-W4-018 supporting) | All green |
