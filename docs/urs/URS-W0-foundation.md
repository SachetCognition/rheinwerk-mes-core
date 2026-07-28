# URS W0 — Foundation

**Rheinwerk MES Consolidation — User Requirements Specification**
Wave: W0 (Foundation) · Source backlog: `docs/waves/W0-foundation.md` (W0-1…W0-8) · Status: Draft for review

---

## 1. Purpose & scope

Wave W0 delivers the platform foundation of the consolidated Rheinwerk MES: the scaffolded Frappe app `rheinwerk_mes` with CI, the canonical master-data entities (Item/Product with UoM conversions, Work Centre, BOM/recipe and production-order anchors), master-data migration tooling with round-trip fixtures for all three legacy sources (Qcadoo/Plant A, OFBiz/Plant B, ERPNext/Plant C), the characterisation-test harness that encodes Qcadoo parity contracts, the evidence-pack generator, and the recorded naming/numbering scheme decision. W0 exit means: canonical entities live, master data from all three sources round-trips, and the regression floor is executing (`docs/waves/W0-foundation.md`, exit statement).

**Out of scope for W0** (delivered by later waves — listed so scope creep is visible):

- Production-order `exec_state` workflow, execution gating hooks, recipe governance workflow, warehouse physical fidelity (Handling Unit / Storage Location / disposal algorithms), draft reservations, shop-floor operator journey, role model, expiry policy decision — **W1** (`docs/waves/W1-production-core.md`).
- Batch genealogy, unified batch object with `qa_state`, batch blocking/quarantine, Quality Inspection wiring, CoA, ISA-88 recipes, hazmat data — **W2** (`docs/waves/W2-traceability-quality.md`).
- Planning/MRP, finite capacity, group-ERP interface, SCADA/OPC-UA — **W3** (`docs/waves/W3-planning-boundary.md`).
- Per-plant cutover, open-batch/genealogy/history backfills, legacy decommission — **W4** (`docs/waves/W4-cutover-decommission.md`). W0 migrates **master data only**; transactional and historical data migration is W2/W4.

## 2. Personas in scope

Subset of the six programme personas relevant to W0 (role model evidence: dossier ch. 3.1 §B.2 — Qcadoo 151-role security model; ch. 3.2 — ERPNext shipped permission model):

| Persona | Fixture name | W0 relevance | Evidence |
|---|---|---|---|
| Technologist | T. Schmid | Owns item master, UoM conversions, BOM/recipe entities | dossier ch. 3.1 §B.2 (master-data / product manager roles `ROLE_PRODUCTS`, `ROLE_PRODUCT_FAMILIES`); ch. 3.2 (`Item Manager`, `Manufacturing Manager`) |
| Planner | P. Krüger | Consumes work centres and production-order entities created in W0 | dossier ch. 3.1 §B.2 (production planner roles); ch. 3.2 (`Manufacturing User`) |
| Warehouse clerk | W. Braun | Validates migrated warehouse master data (warehouses, items, UoM) | dossier ch. 3.1 §B.2 (warehouse operator roles) |
| Business viewer | B. Vogel | Reads the wave-exit evidence pack | dossier §6.2 platform-substrate row (reporting) |

Shop-floor operator (O. Weber) and quality inspector (Q. Fischer) enter scope in W1 and W2 respectively.

## 3. Requirements

### 3.1 Platform scaffold & CI (W0-1)

#### URS-W0-001 — Scaffold the `rheinwerk_mes` Frappe app

The system shall provide a Frappe application `rheinwerk_mes` with module skeletons for the target modules named in the disposition table (manufacturing_core, execution_gating, genealogy, quality, warehouse, recipe_isa88, regulatory_hazmat, integration), installable on the ERPNext substrate without modifying (forking) any anchor DocType, so that the technologist and planner work on one platform.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext substrate · dossier ch. 3.2 §D (healthiest platform: 515 test files, CI workflows); ADR-001; module list from `CONSOLIDATION.md`
- **Acceptance criteria:**
  - **AC-1** Given a clean ERPNext site, When `rheinwerk_mes` is installed, Then installation completes without error and all eight module skeletons are registered in the app's `modules.txt`.
  - **AC-2** Given the installed app, When the list of anchor DocTypes (Item, Workstation, BOM, Work Order, Warehouse, UOM) is compared to stock ERPNext, Then no anchor DocType schema file inside ERPNext has been modified — all extensions exist only as custom fields or linked DocTypes in `rheinwerk_mes`.
- **Dependencies:** none (wave entry).

#### URS-W0-002 — Continuous integration with lint and test runner

The system shall run an automated CI pipeline (lint + test runner) on every change to the `rheinwerk_mes` app, so that the regression floor required by the W0 exit criterion is executing from the first commit.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext substrate practices · dossier ch. 3.2 §D (GitHub Actions `server-tests-mariadb.yml`, `linters.yml`); W0-1 backlog item
- **Acceptance criteria:**
  - **AC-1** Given a pull request that introduces a lint violation, When CI runs, Then the lint job fails and the pipeline result is red.
  - **AC-2** Given a pull request that breaks an existing test, When CI runs, Then the test job fails and reports the failing test by name.
  - **AC-3** Given a clean pull request, When CI runs, Then lint and test jobs both pass and the pipeline result is green.
- **Dependencies:** URS-W0-001.

### 3.2 Canonical master data (W0-2)

#### URS-W0-003 — Canonical Item/Product master

The system shall provide the canonical Item master on the anchor ERPNext `Item` DocType, with field mappings recorded from Qcadoo `product`, ERPNext `Item`, and OFBiz `Product`, so that the technologist maintains one item master for all plants.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext master data · dossier §5.2 (master data Rich in all three); §6.2 master-data row; `docs/canonical-model/README.md` conventions
- **Acceptance criteria:**
  - **AC-1** Given the installed app, When the technologist T. Schmid creates item RW-CHM-0001 "Rheinol 40 Basisharz" with stock UoM kg and default pack "25 kg sack", Then the item saves and appears in the Item list with those values.
  - **AC-2** Given items RW-CHM-0001, RW-CHM-0002 "Additiv K7" and RW-CHM-0003 "Rheinol 40 Compound" exist, When each is opened, Then a `legacy_refs`-style mapping record shows its source system identifier (Qcadoo product number / ERPNext item_code / OFBiz productId) where migrated.
- **Dependencies:** URS-W0-001.

#### URS-W0-004 — Unit-of-measure conversions

The system shall support item-level UoM conversion factors (e.g. sack ↔ kg) equivalent to Qcadoo `unitConversionItem` semantics on the anchor UoM conversion mechanism, so that quantities entered in pack units resolve deterministically to stock UoM.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext master data · dossier ch. 3.1 §B.3 (`basic/model/product.xml:55` unit conversions); §5.2 master-data comparison
- **Acceptance criteria:**
  - **AC-1** Given item RW-CHM-0001 with conversion 1 sack = 25 kg, When the planner enters a quantity of 20 sack on any W0 fixture transaction, Then the system resolves it to 500 kg stock UoM with no rounding drift.
  - **AC-2** Given item RW-CHM-0002 with conversion 1 pail = 5 kg, When an invalid conversion factor 0 is entered, Then the save is rejected with a field-level validation message.
- **Dependencies:** URS-W0-003.

### 3.3 Canonical Work Centre (W0-3)

#### URS-W0-005 — Canonical Work Centre entity

The system shall provide the canonical Work Centre on the anchor `Workstation` (+ `Workstation Type`), extended with `production_line` (Link) and `division` (Link, plant-area tree), mapping Qcadoo workstation/productionLine, ERPNext Workstation, and OFBiz FixedAsset machine groups, so that planners address machines as operational resources while asset accounting stays with the group ERP.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext Workstation · ADR-010 / CDM-08; dossier §5.2 work-centre row (OFBiz models machines as accounting assets)
- **Acceptance criteria:**
  - **AC-1** Given the installed app, When work centres LINE-1/MIX-01 and LINE-1/FILL-01 are created with `production_line` = LINE-1, Then both save and a filter on `production_line` = LINE-1 returns exactly these two workstations.
  - **AC-2** Given an OFBiz FixedAsset machine-group extract, When it is migrated, Then a Workstation record is created and no asset-ledger (accounting) record is created in the MES.
- **Dependencies:** URS-W0-001.

### 3.4 Canonical BOM/recipe & production-order entities (W0-4)

#### URS-W0-006 — Canonical BOM/recipe anchor entities

The system shall use the anchor ERPNext `BOM` and `Routing` DocTypes, unforked, as the canonical recipe base, so that recipe data for all plants lands on one versioned model (governance workflow follows in W1).

- **Priority:** Must
- **Lineage:** Adopt · ERPNext BOM/Work Order · dossier §6.2 recipe/BOM golden source = ERPNext (`bom.py:429-440`, `bom.py:620-637`); ADR-006 / CDM-04
- **Acceptance criteria:**
  - **AC-1** Given items RW-CHM-0001, RW-CHM-0002 and RW-CHM-0003 exist, When the technologist creates BOM-RW-CHM-0003-001 for RW-CHM-0003 consuming RW-CHM-0001 and RW-CHM-0002 with routing RT-COMPOUND-01 (operations at LINE-1/MIX-01 then LINE-1/FILL-01), Then the BOM and Routing save and submit on anchor DocTypes with no schema fork.
  - **AC-2** Given the submitted BOM, When a new BOM version for RW-CHM-0003 is created, Then the anchor versioned naming (`BOM-<item>-<n>`) distinguishes the versions.
- **Dependencies:** URS-W0-003, URS-W0-005.

#### URS-W0-007 — Canonical production-order anchor entity

The system shall use the anchor ERPNext `Work Order` DocType, unforked, as the canonical production-order base, with the CDM-02 extension fields (`production_line`, `master_order`, `state_history` container) present but the `exec_state` workflow deferred to W1, so that W1 can layer the state machine without schema rework.

- **Priority:** Must
- **Lineage:** Adopt (anchor) · ERPNext Work Order · ADR-004 / CDM-02; dossier §5.2 production-order row
- **Acceptance criteria:**
  - **AC-1** Given BOM-RW-CHM-0003-001 exists, When the planner P. Krüger creates production order PO-2026-0001 for 500 kg RW-CHM-0003 on `production_line` LINE-1, Then the Work Order saves with the extension fields populated and the anchor DocType remains unforked.
  - **AC-2** Given PO-2026-0001, When its fields are inspected via the API, Then `production_line` and `master_order` are exposed as `rheinwerk_mes` custom fields, not anchor-schema modifications.
- **Dependencies:** URS-W0-005, URS-W0-006.

### 3.5 Master-data migration tooling (W0-5)

#### URS-W0-008 — Qcadoo (Plant A) master-data extractor

The system shall provide an extractor that reads item/product, UoM-conversion, work-centre (workstation/productionLine/division) and technology-header master data from the Qcadoo PostgreSQL schema into the canonical import format, so that Plant A master data migrates as a data-model migration, not a copy.

- **Priority:** Must
- **Lineage:** Migration (no disposition) · source Qcadoo · dossier §7 implication 4; ch. 3.1 §B.3 (`basic/model/product.xml`, `basic/model/division.xml`); CDM-03/CDM-08 mapping rows
- **Acceptance criteria:**
  - **AC-1** Given the Plant A round-trip fixture set (containing a product mapping to RW-CHM-0001 with unit conversion 1 sack = 25 kg), When the extractor runs, Then a canonical import file is produced whose record count equals the fixture source count.
  - **AC-2** Given the extract, When it is imported, Then RW-CHM-0001 exists with the conversion intact and its Qcadoo product number recorded in the legacy mapping.
- **Dependencies:** URS-W0-003, URS-W0-004, URS-W0-005.

#### URS-W0-009 — ERPNext (Plant C) master-data extractor

The system shall provide an extractor for ERPNext DocType master data (Item, UOM Conversion, Workstation, BOM headers, Warehouse) from the Plant C instance into the canonical import format, preserving identity fields unchanged where the anchor model is identical.

- **Priority:** Must
- **Lineage:** Migration · source ERPNext · dossier §7 implication 4; CDM mapping legend (`=` direct) `docs/canonical-model/README.md`
- **Acceptance criteria:**
  - **AC-1** Given the Plant C fixture export containing item RW-CHM-0002 and warehouse "FG Lager Süd", When the extractor runs and the import is executed, Then both records exist in the target with field values byte-identical for directly-mapped (`=`) fields.
- **Dependencies:** URS-W0-003, URS-W0-005, URS-W0-006.

#### URS-W0-010 — OFBiz (Plant B) master-data extractor

The system shall provide an extractor for OFBiz entity XML/Derby exports covering Product, FixedAsset machine groups, and facility (warehouse) master data into the canonical import format, applying the CDM-08 rule that machine FixedAssets import as Workstations only (asset accounting stays with group ERP).

- **Priority:** Must
- **Lineage:** Migration (Retire OFBiz per CONSOLIDATION.md) · source OFBiz · dossier §7 implication 4 and implication 9; ADR-010 consequence; ch. 3.3 (`product-entitymodel.xml`, `accounting-entitymodel.xml:630`)
- **Acceptance criteria:**
  - **AC-1** Given the Plant B fixture export containing a Product mapping to RW-CHM-0003 and one machine FixedAsset, When the extractor runs and the import executes, Then the item exists and exactly one Workstation is created for the FixedAsset with no accounting record.
  - **AC-2** Given a Product without a UoM equivalent, When extracted, Then the record is written to an exceptions report rather than silently defaulted.
- **Dependencies:** URS-W0-003, URS-W0-005.

#### URS-W0-011 — Master-data round-trip reconciliation

The system shall verify the master-data migration by round-trip: for each of the three sources, extract → import → re-export and reconcile against the source fixture with record counts and field-level spot checks, producing a per-source reconciliation report with a deterministic pass/fail, so that the W0 exit criterion "master data from all three sources round-trips" is demonstrable.

- **Priority:** Must
- **Lineage:** Migration · all three sources · W0-5 backlog item; dossier §7 implication 4; wave exit statement `docs/waves/W0-foundation.md`
- **Acceptance criteria:**
  - **AC-1** Given the three fixture sets, When the round-trip runs for each source, Then each reconciliation report shows source count = imported count = re-exported count for items, work centres and warehouses, and status PASS.
  - **AC-2** Given a fixture deliberately mutated after import (one item renamed), When reconciliation runs, Then the report shows status FAIL naming the mismatched record.
  - **AC-3** Given a PASS report, When rollback is invoked on a failed run, Then all records imported by that run are removed and a re-run reconciliation of the untouched fixtures still passes (rollback condition).
- **Dependencies:** URS-W0-008, URS-W0-009, URS-W0-010.

### 3.6 Characterisation-test harness (W0-6)

#### URS-W0-012 — Characterisation harness with executable parity contracts

The system shall provide a characterisation-test harness that encodes, as executable parity contracts against fixture data: (a) Qcadoo order-acceptance/completion gating, (b) Qcadoo technology structural validators, and (c) Qcadoo FEFO picking order — so that W1 re-implementations are validated against legacy behaviour, never ported code.

- **Priority:** Must
- **Lineage:** Absorb · Qcadoo semantics · `OrderStateValidationService.java:44-63`; `TechnologyValidationService.java:91-707`; `ResourceManagementServiceImpl.java:1015-1027` + `WarehouseAlgorithm.java:26-27`; ADR-001 consequence (characterisation tests are the parity contract); dossier §7 implication 1
- **Acceptance criteria:**
  - **AC-1** Given the harness fixture "order without dateFrom/dateTo/production line/technology", When the acceptance-gate contract executes, Then it asserts refusal — matching `OrderStateValidationService.java:44-47`.
  - **AC-2** Given the harness fixture "order with doneQuantity = 0", When the completion-gate contract executes, Then it asserts refusal — matching `OrderStateValidationService.java:54-63`.
  - **AC-3** Given fixture batches BATCH-A-0001 (expiry 31.12.2026) and BATCH-A-0002 (expiry 30.06.2026) in an FEFO warehouse fixture, When the FEFO contract executes, Then it asserts pick order BATCH-A-0002 before BATCH-A-0001 — matching `ResourceManagementServiceImpl.java:1015-1027`.
  - **AC-4** Given the CI pipeline (URS-W0-002), When any pipeline run executes, Then the harness contracts run as part of the regression floor and a contract failure fails the pipeline.
- **Dependencies:** URS-W0-001, URS-W0-002.

### 3.7 Evidence-pack generator (W0-7)

#### URS-W0-013 — Wave-exit evidence-pack generator

The system shall generate a wave-exit evidence report linking each backlog item of a wave to its dossier findings and to the code/tests that implement and verify it, so that the business viewer can audit wave exit without reading source code.

- **Priority:** Should
- **Lineage:** Programme tooling (no disposition) · — · `docs/evidence/README.md` audit spine; W0-7 backlog item
- **Acceptance criteria:**
  - **AC-1** Given W0 items W0-1…W0-8 with their URS and test IDs recorded, When the generator runs for W0, Then it emits a report with one row per backlog item showing item → dossier citation → URS ID(s) → test ID(s), with zero unlinked items.
  - **AC-2** Given a backlog item deliberately stripped of its test link in fixture data, When the generator runs, Then that item is flagged as evidence-incomplete rather than omitted.
- **Dependencies:** URS-W0-002, URS-W0-012.

### 3.8 Naming/numbering scheme (W0-8)

#### URS-W0-014 — Naming-series decision applied estate-wide

The system shall use ERPNext naming series (not DB-trigger sequences) for all canonical entities, with the series formats for batches (`BATCH-{plant}-{#}`), production orders (`PO-{YYYY}-{#}`) and handling units (`HU-{#}`) recorded in a decision note, and legacy Qcadoo trigger-generated numbers preserved in `legacy_refs`, so that numbering is platform-native and legacy identifiers remain queryable.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext naming series · dossier ch. 3.1 §C.3 (`mes_db_en.sql:1044`, `:1140-1183` trigger-generated numbers) vs ch. 3.2 naming series; CDM-01 `batch_id` series; W0-8 backlog item
- **Acceptance criteria:**
  - **AC-1** Given the naming decision note exists in the repo, When production order PO-2026-0001 and (in W2 fixture form) batch BATCH-A-0001 are created, Then their identifiers match the recorded series formats.
  - **AC-2** Given a migrated Plant A record with Qcadoo trigger number "000123/2025", When the record is opened, Then the legacy number is visible in its `legacy_refs` entry.
- **Dependencies:** URS-W0-003, URS-W0-006, URS-W0-007.

## 4. Non-functional requirements

#### URS-W0-015 — Audit trail on canonical master-data changes

The system shall record every create/update/delete of canonical master-data entities (Item, Workstation, BOM, Work Order) with user, timestamp and changed fields, using the platform version/audit mechanism, retrievable per record.

- **Priority:** Must
- **Lineage:** Adopt · ERPNext substrate (Frappe document versioning, dossier ch. 3.2 §D persistence model) · supports dossier §6.3 e-signature white-space boundary (audit rows exist; e-signatures are a W2 decision)
- **Acceptance criteria:**
  - **AC-1** Given item RW-CHM-0001, When T. Schmid changes the item name and saves, Then the version log shows T. Schmid, the timestamp, and the old→new value of the changed field.

#### URS-W0-016 — German-first internationalisation baseline

The system shall externalise all `rheinwerk_mes` UI strings with German as the first-class locale, and render dates as DD.MM.YYYY and mass quantities in kg on all W0 screens.

- **Priority:** Must
- **Lineage:** Design conformance · `rheinwerk-mes-design-SKILL.md` §"Content and language" (German-first i18n discipline, DD.MM.YYYY, kg) · dossier ch. 3.1 §B.1 (legacy locale files incl. de)
- **Acceptance criteria:**
  - **AC-1** Given the site locale is de, When batch fixture BATCH-A-0001's expiry is displayed on any W0 screen, Then it renders as 31.12.2026.
  - **AC-2** Given the `rheinwerk_mes` codebase, When scanned for hard-coded user-facing strings and string concatenation in translatable text, Then zero occurrences are found.
- **Design conformance:** status pills, when present on W0 list views, render icon + label + colour per design skill §"Component rules"; identifiers (item codes, order numbers) render in mono per §"Typography".

#### URS-W0-017 — Access control baseline

The system shall restrict creation and modification of canonical master data to the technologist role set, with the planner and warehouse clerk read-only on master data, using per-DocType RBAC as the W0 baseline (workflow-state-level permissions follow in W1).

- **Priority:** Must
- **Lineage:** Adopt · ERPNext RBAC (dossier ch. 3.2 personas/roles; §6.2 platform-substrate row) · role-model levelling deferred per dossier §7 implication 7
- **Acceptance criteria:**
  - **AC-1** Given P. Krüger holds only the planner role, When she attempts to edit item RW-CHM-0001, Then the save is refused with a permission error.
  - **AC-2** Given T. Schmid holds the technologist role, When he edits RW-CHM-0001, Then the save succeeds.

#### URS-W0-018 — Migration tooling performance and determinism

The system shall complete a full master-data round-trip (extract → import → re-export → reconcile) for each source fixture set in under 30 minutes on the CI runner, and shall produce byte-identical canonical import files on repeated runs over unchanged fixtures.

- **Priority:** Should
- **Lineage:** Migration tooling NFR · derived from W0-5 and the CI regression-floor exit statement (`docs/waves/W0-foundation.md`)
- **Acceptance criteria:**
  - **AC-1** Given the three fixture sets, When the round-trip runs in CI, Then each source completes within 30 minutes wall-clock.
  - **AC-2** Given an unchanged fixture set, When the extractor runs twice, Then the two output files are byte-identical (deterministic ordering).

## 5. Data migration requirements

W0 lands **master data** from all three sources (W0-5). The migration requirements are URS-W0-008…URS-W0-011 above; this section states the mapping, reconciliation and rollback frame they must satisfy:

- **Source → canonical mapping:** per CDM sections — Item/UoM (CDM-03 conventions, `docs/canonical-model/README.md` §CDM-03 mapping), Work Centre (CDM-08 mapping table), BOM headers (CDM-04 mapping), warehouse structure (CDM-03). Mapping legend `=`/`≈`/`∅`/`✕` applies; every `≈` transform is documented in the extractor.
- **Reconciliation criteria:** record counts per entity per source; field-level spot checks on a deterministic 5 % sample (minimum 10 records) per entity; checksum comparison on directly-mapped (`=`) fields. Report per source per URS-W0-011.
- **Rollback condition:** any FAIL reconciliation report blocks W0 exit; the failed run's imports are reversed per URS-W0-011 AC-3 before re-run.

## 6. Wave exit criteria

Restated from `docs/waves/W0-foundation.md` ("canonical entities live; master data from all three sources round-trips; regression floor executing") and decomposed:

| ID | Check | Verified by |
|---|---|---|
| EXIT-W0-1 | Canonical Item, Work Centre, BOM/Routing and Work Order (anchor + extensions) are live: creatable via UI/API with fixture data | URS-W0-003…007 acceptance criteria |
| EXIT-W0-2 | Master data from Qcadoo, ERPNext and OFBiz fixture sets round-trips with PASS reconciliation reports for all three sources | URS-W0-008…011 |
| EXIT-W0-3 | Regression floor executing: CI runs lint, tests and the characterisation contracts on every change and fails on any contract breach | URS-W0-002, URS-W0-012 |
| EXIT-W0-4 | Naming-series decision recorded and applied; evidence pack for W0 generated with zero unlinked backlog items | URS-W0-013, URS-W0-014 |

## 7. Untraceable / deferred

- None untraceable. All requirements above trace to W0 backlog items, ADRs or the design skill.
- Deferred by design: `exec_state` workflow (W1), `qa_state`/Batch object (W2 — referenced by fixtures only), workflow-state-level permissions (W1 per dossier §7 implication 7).
- Open question dependency: dossier §8.2 Q1 (Plant C operated settings) does not block W0 but must be answered before W1 gating exits.
