# TST W0 — Foundation

**Rheinwerk MES Consolidation — Test & Verification**
Wave: W0 (Foundation) · Verifies: `docs/urs/URS-W0-foundation.md` · Status: Draft for review

---

## 1. Test strategy

**Levels.** Unit tests are assumed inside the `rheinwerk_mes` app (CI-enforced, URS-W0-002) and are not enumerated here. This document specifies:

- **Integration** — canonical entities on the ERPNext substrate (DocType creation, no-fork checks, naming series).
- **Journey/acceptance** — persona-driven flows (technologist creates master data; business viewer reads evidence pack).
- **Migration reconciliation** — extract → import → re-export round-trips for all three sources with count/checksum/spot-check reports and rollback.
- **Characterisation-parity** — the harness itself is under test in W0: contracts must encode the legacy behaviours and fail correctly.
- **NFR** — audit trail, i18n, access control, tooling performance/determinism.
- **Design-conformance** — W0 baseline (mono identifiers, status pills on list views, DD.MM.YYYY/kg rendering).

**Environments.** (1) CI runner: clean ERPNext site + `rheinwerk_mes`, fixture-seeded, MariaDB/PostgreSQL per CI matrix; (2) integration site for manual journey checks. Migration tests run against the committed fixture exports for Plant A (Qcadoo PostgreSQL dump subset), Plant B (OFBiz entity XML), Plant C (ERPNext DocType export) — never against live plants.

**Test data.** Shared programme fixtures: items RW-CHM-0001 "Rheinol 40 Basisharz" (25 kg sack), RW-CHM-0002 "Additiv K7" (5 kg pail), RW-CHM-0003 "Rheinol 40 Compound" (FG); batches BATCH-A-0001 (500 kg, expiry 31.12.2026) and BATCH-A-0002 (50 kg, expiry 30.06.2026) as harness fixtures; production orders PO-2026-0001/PO-2026-0002; work centres LINE-1/MIX-01, LINE-1/FILL-01; warehouses RM Lager Nord (FEFO), FG Lager Süd (FIFO); storage location NORD-A-01-01; BOM-RW-CHM-0003-001 with routing RT-COMPOUND-01. Personas: T. Schmid (technologist), P. Krüger (planner), W. Braun (warehouse clerk), B. Vogel (business viewer).

## 2. Traceability matrix

| URS ID | Test cases | | Test case | URS ID(s) |
|---|---|---|---|---|
| URS-W0-001 | TC-W0-001, TC-W0-002 | | TC-W0-001 | URS-W0-001 |
| URS-W0-002 | TC-W0-003 | | TC-W0-002 | URS-W0-001 |
| URS-W0-003 | TC-W0-004 | | TC-W0-003 | URS-W0-002 |
| URS-W0-004 | TC-W0-005 | | TC-W0-004 | URS-W0-003 |
| URS-W0-005 | TC-W0-006 | | TC-W0-005 | URS-W0-004 |
| URS-W0-006 | TC-W0-007 | | TC-W0-006 | URS-W0-005 |
| URS-W0-007 | TC-W0-008 | | TC-W0-007 | URS-W0-006 |
| URS-W0-008 | TC-W0-009 | | TC-W0-008 | URS-W0-007 |
| URS-W0-009 | TC-W0-010 | | TC-W0-009 | URS-W0-008 |
| URS-W0-010 | TC-W0-011 | | TC-W0-010 | URS-W0-009 |
| URS-W0-011 | TC-W0-012, TC-W0-013 | | TC-W0-011 | URS-W0-010 |
| URS-W0-012 | TC-W0-014, TC-W0-015 | | TC-W0-012 | URS-W0-011 |
| URS-W0-013 | TC-W0-016 | | TC-W0-013 | URS-W0-011 |
| URS-W0-014 | TC-W0-017 | | TC-W0-014 | URS-W0-012 |
| URS-W0-015 | TC-W0-018 | | TC-W0-015 | URS-W0-012 |
| URS-W0-016 | TC-W0-019 | | TC-W0-016 | URS-W0-013 |
| URS-W0-017 | TC-W0-020 | | TC-W0-017 | URS-W0-014 |
| URS-W0-018 | TC-W0-021 | | TC-W0-018 | URS-W0-015 |
| — | — | | TC-W0-019 | URS-W0-016 |
| — | — | | TC-W0-020 | URS-W0-017 |
| — | — | | TC-W0-021 | URS-W0-018 |

No orphans in either direction (18 URS ↔ 21 TC).

## 3. Test cases

### TC-W0-001 — App installs with module skeletons *(Integration)*
- **Objective:** verify `rheinwerk_mes` installs and registers all eight modules. **URS:** URS-W0-001.
- **Preconditions:** clean ERPNext site.
- **Steps:**
  1. Install app `rheinwerk_mes`. → Install completes exit code 0, no error log entries.
  2. Read the app's `modules.txt`. → Contains manufacturing_core, execution_gating, genealogy, quality, warehouse, recipe_isa88, regulatory_hazmat, integration.
- **Pass/fail:** all eight modules present and install clean; else fail.

### TC-W0-002 — No anchor DocType fork *(Integration)*
- **Objective:** anchor DocTypes are unmodified. **URS:** URS-W0-001.
- **Preconditions:** TC-W0-001 passed.
- **Steps:**
  1. Diff Item, Workstation, BOM, Work Order, Warehouse, UOM schema files against stock ERPNext at the pinned version. → Zero diffs.
  2. List `rheinwerk_mes` custom fields on those DocTypes. → All extensions are Custom Field / linked DocType records owned by `rheinwerk_mes`.
- **Pass/fail:** zero anchor schema diffs; else fail.

### TC-W0-003 — CI gates lint and test failures *(Integration)*
- **Objective:** regression floor is executing. **URS:** URS-W0-002.
- **Steps:**
  1. Push a branch with a deliberate lint violation. → Lint job fails, pipeline red.
  2. Push a branch breaking one test. → Test job fails naming the test, pipeline red.
  3. Push a clean branch. → Both jobs pass, pipeline green.
- **Pass/fail:** all three outcomes as expected.

### TC-W0-004 — Item master with legacy refs *(Journey)*
- **Objective:** technologist creates canonical items. **URS:** URS-W0-003.
- **Preconditions:** T. Schmid logged in with technologist role.
- **Steps:**
  1. Create RW-CHM-0001 "Rheinol 40 Basisharz", stock UoM kg, pack "25 kg sack". → Saves; appears in Item list.
  2. Create RW-CHM-0002 "Additiv K7" and RW-CHM-0003 "Rheinol 40 Compound" (FG). → Both save.
  3. Open a migrated fixture item. → Legacy mapping shows the source-system identifier.
- **Pass/fail:** all three items exist with correct values and legacy refs where migrated.

### TC-W0-005 — UoM conversion resolution *(Integration)*
- **Objective:** pack-unit quantities resolve deterministically. **URS:** URS-W0-004.
- **Preconditions:** RW-CHM-0001 with 1 sack = 25 kg; RW-CHM-0002 with 1 pail = 5 kg.
- **Steps:**
  1. Enter 20 sack of RW-CHM-0001 on a fixture transaction. → Resolves to exactly 500 kg.
  2. Attempt to save conversion factor 0 on RW-CHM-0002. → Field-level validation rejects the save.
- **Pass/fail:** exact 500 kg with no rounding drift and factor-0 rejected.

### TC-W0-006 — Work Centre with production line; OFBiz asset separation *(Integration)*
- **Objective:** CDM-08 entity behaviour. **URS:** URS-W0-005.
- **Steps:**
  1. Create LINE-1/MIX-01 and LINE-1/FILL-01 with `production_line` = LINE-1. → Both save; filter on LINE-1 returns exactly these two.
  2. Import the Plant B FixedAsset machine-group fixture. → Workstation created; query asset/accounting tables → zero MES asset records.
- **Pass/fail:** filter result exact and no accounting record created.

### TC-W0-007 — BOM/Routing anchors and versioning *(Integration)*
- **Objective:** canonical recipe base on unforked anchors. **URS:** URS-W0-006.
- **Preconditions:** TC-W0-004, TC-W0-006 passed.
- **Steps:**
  1. Create BOM-RW-CHM-0003-001 (consumes RW-CHM-0001 + RW-CHM-0002; routing RT-COMPOUND-01 with MIX at LINE-1/MIX-01, FILL at LINE-1/FILL-01); submit. → Saves and submits.
  2. Create a second BOM version for RW-CHM-0003. → Anchor versioned naming `BOM-…-2` distinguishes it.
- **Pass/fail:** both steps as expected on anchor DocTypes.

### TC-W0-008 — Work Order anchor with extension fields *(Integration)*
- **Objective:** production-order base ready for W1 layering. **URS:** URS-W0-007.
- **Steps:**
  1. As P. Krüger create PO-2026-0001, 500 kg RW-CHM-0003, `production_line` LINE-1, BOM-RW-CHM-0003-001. → Saves with extension fields populated.
  2. Fetch PO-2026-0001 via API; inspect field ownership. → `production_line`, `master_order` are `rheinwerk_mes` custom fields.
- **Pass/fail:** order saves and fields are custom, not anchor-schema.

### TC-W0-009 — Qcadoo extractor round trip *(Migration)*
- **Objective:** Plant A master data extracts and imports. **URS:** URS-W0-008.
- **Preconditions:** Plant A fixture set loaded.
- **Steps:**
  1. Run the Qcadoo extractor. → Canonical import file produced; record count = fixture source count.
  2. Import; open RW-CHM-0001. → Conversion 1 sack = 25 kg intact; Qcadoo product number in legacy mapping.
- **Pass/fail:** counts equal and mapped fields intact.

### TC-W0-010 — ERPNext extractor identity preservation *(Migration)*
- **Objective:** Plant C direct-mapped fields byte-identical. **URS:** URS-W0-009.
- **Steps:**
  1. Run extractor on the Plant C fixture (contains RW-CHM-0002, warehouse "FG Lager Süd"); import. → Both records exist.
  2. Compare `=`-mapped field values source vs target. → Byte-identical.
- **Pass/fail:** zero differences on direct-mapped fields.

### TC-W0-011 — OFBiz extractor with exceptions report *(Migration)*
- **Objective:** Plant B extraction honours CDM-08 rule and reports exceptions. **URS:** URS-W0-010.
- **Steps:**
  1. Run extractor on Plant B fixture (Product → RW-CHM-0003, one machine FixedAsset); import. → Item exists; exactly one Workstation; no accounting record.
  2. Include a Product with unmappable UoM; re-run. → Record lands in exceptions report, not silently defaulted.
- **Pass/fail:** both behaviours exact.

### TC-W0-012 — Three-source round-trip reconciliation PASS/FAIL *(Migration)*
- **Objective:** W0 exit reconciliation works and detects mismatches. **URS:** URS-W0-011.
- **Steps:**
  1. Run extract → import → re-export → reconcile for Qcadoo, ERPNext, OFBiz fixtures. → Three reports; each shows source = imported = re-exported counts for items, work centres, warehouses; status PASS.
  2. Rename one imported item; re-run reconciliation. → Status FAIL naming the mismatched record.
- **Pass/fail:** three PASS reports in step 1 and a named FAIL in step 2.

### TC-W0-013 — Migration rollback *(Migration)*
- **Objective:** failed runs are reversible. **URS:** URS-W0-011 (AC-3).
- **Steps:**
  1. Force a FAIL run (mutated fixture); invoke rollback. → All records imported by that run removed.
  2. Re-run reconciliation on untouched fixtures. → PASS.
- **Pass/fail:** rollback complete and clean re-run passes.

### TC-W0-014 — Characterisation contracts encode legacy gates *(Parity)*
- **Objective:** harness asserts Qcadoo gating and FEFO order. **URS:** URS-W0-012.
- **Legacy baseline cited:** `OrderStateValidationService.java:44-47` (accept), `:54-63` (complete), `ResourceManagementServiceImpl.java:1015-1027` (FEFO), `TechnologyValidationService.java:91-707` (validators).
- **Steps:**
  1. Run the acceptance-gate contract on fixture "order missing dates/line/technology". → Asserts refusal.
  2. Run the completion-gate contract on fixture "doneQuantity = 0". → Asserts refusal.
  3. Run the FEFO contract on BATCH-A-0001 (31.12.2026) + BATCH-A-0002 (30.06.2026). → Asserts pick order BATCH-A-0002 first.
- **Pass/fail:** all contracts execute and assert the legacy behaviour.

### TC-W0-015 — Contract failure fails CI *(Parity)*
- **Objective:** parity contracts are part of the regression floor. **URS:** URS-W0-012 (AC-4).
- **Steps:**
  1. Introduce a deliberate contract-breaking change on a branch; push. → CI runs the harness; pipeline red naming the contract.
  2. Revert; push. → Pipeline green.
- **Pass/fail:** red then green as expected.

### TC-W0-016 — Evidence pack completeness *(Integration)*
- **Objective:** wave-exit report links items → findings → code/tests. **URS:** URS-W0-013.
- **Steps:**
  1. Run generator for W0. → One row per W0-1…W0-8: item → dossier citation → URS ID(s) → test ID(s); zero unlinked.
  2. Strip one item's test link in fixture data; re-run. → Item flagged evidence-incomplete, not omitted.
- **Pass/fail:** complete report and correct flagging.

### TC-W0-017 — Naming series applied; legacy numbers preserved *(Integration)*
- **Objective:** W0-8 decision enforced. **URS:** URS-W0-014.
- **Steps:**
  1. Verify decision note exists in repo; create PO-2026-0001 and fixture batch BATCH-A-0001. → Identifiers match recorded series formats.
  2. Open a migrated Plant A record with trigger number "000123/2025". → Legacy number visible in `legacy_refs`.
- **Pass/fail:** formats match and legacy number visible.

### TC-W0-018 — Master-data audit trail *(NFR)*
- **Objective:** version log on changes. **URS:** URS-W0-015.
- **Steps:**
  1. As T. Schmid rename RW-CHM-0001; save. → Version log records T. Schmid, timestamp, old→new value.
- **Pass/fail:** all three elements present.

### TC-W0-019 — German-first rendering *(Design-conformance)*
- **Objective:** i18n baseline. **URS:** URS-W0-016.
- **Steps:**
  1. With locale de, display BATCH-A-0001 expiry on a W0 screen. → Renders 31.12.2026.
  2. Scan `rheinwerk_mes` code for hard-coded user-facing strings / concatenation. → Zero occurrences.
  3. Inspect a W0 list view: identifiers mono; any status pill = icon + label + colour.
- **Pass/fail:** all three checks pass.

### TC-W0-020 — Access-control baseline *(NFR)*
- **Objective:** role restrictions on master data. **URS:** URS-W0-017.
- **Steps:**
  1. As P. Krüger (planner only) edit RW-CHM-0001. → Permission error; no change saved.
  2. As T. Schmid (technologist) edit RW-CHM-0001. → Save succeeds.
- **Pass/fail:** refusal then success exactly as specified.

### TC-W0-021 — Tooling performance and determinism *(NFR)*
- **Objective:** migration NFRs. **URS:** URS-W0-018.
- **Steps:**
  1. Run full round-trip per source on the CI runner; measure wall-clock. → Each < 30 minutes.
  2. Run the extractor twice on unchanged fixtures; compare outputs. → Byte-identical.
- **Pass/fail:** both thresholds met.

## 4. Parity test section (Absorb scope)

W0's Absorb scope is the characterisation harness itself (W0-6). The parity baseline is Qcadoo legacy code, encoded as executable contracts:

| Contract | Legacy code path (baseline) | Target assertion | Verified by |
|---|---|---|---|
| Order acceptance gate (dates/line/technology required) | `orders/states/OrderStateValidationService.java:44-47` | Refusal on missing fields | TC-W0-014 step 1 |
| Order completion gate (doneQuantity = 0 blocks) | `OrderStateValidationService.java:54-63` | Refusal on zero output | TC-W0-014 step 2 |
| FEFO picking order (expiry ascending) | `ResourceManagementServiceImpl.java:1015-1027`; `WarehouseAlgorithm.java:26-27` | BATCH-A-0002 (30.06.2026) picked before BATCH-A-0001 (31.12.2026) | TC-W0-014 step 3 |
| Technology structural validators (tree/units/in-use) | `TechnologyValidationService.java:91-707` | Validator refusal fixtures encoded | TC-W0-014 (fixtures), consumed by W1 |

Deliberate deviations: **none in W0**. (The expiry-policy divergence is a W1 decision, URS-W1-030; its characterisation delta is recorded there.)

## 5. Wave acceptance checklist

Executable form of the W0 exit criteria (`docs/urs/URS-W0-foundation.md` §6); this checklist closes the W0 Epic.

| Exit ID | Check | Test cases | Result |
|---|---|---|---|
| EXIT-W0-1 | Canonical Item, Work Centre, BOM/Routing, Work Order live with fixture data | TC-W0-001, TC-W0-002, TC-W0-004…008 | ☐ |
| EXIT-W0-2 | Master data from all three sources round-trips (PASS reports, rollback proven) | TC-W0-009…013 | ☐ |
| EXIT-W0-3 | Regression floor executing (CI + characterisation contracts gate merges) | TC-W0-003, TC-W0-014, TC-W0-015 | ☐ |
| EXIT-W0-4 | Naming decision recorded/applied; W0 evidence pack complete | TC-W0-016, TC-W0-017 | ☐ |
| — (NFR floor) | Audit, i18n, access control, tooling NFRs | TC-W0-018…021 | ☐ |
