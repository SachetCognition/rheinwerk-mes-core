# URS W4 — Cutover & Decommission

**Programme:** Rheinwerk Chemie GmbH MES consolidation — User Requirements Specification, Wave W4
**Sources:** `docs/40-planning/cutover-decommission/W4-cutover-decommission.md` (W4-1…W4-7) · `docs/40-planning/CONSOLIDATION.md` · `docs/30-architecture/adr/ADR-003/004/005` · `docs/30-architecture/canonical-model/README.md` (CDM-01, CDM-02, CDM-03) · `docs/10-discovery/dossier/production-systems-dossier.md` §3.1/§3.3, §5.3, §7 (implications 4, 9, 10), §8.2 (#2, #3, #7) · `.agents/skills/rheinwerk-mes-design/SKILL.md`
**Requirement count:** 14 (within the 10–15 sizing guide).

---

## 1. Purpose & scope

Wave W4 moves all three plants onto the consolidated MES and retires the legacy estate: per-plant, per-journey cutover runbooks; the Plant A data backfill (lot-level `Resource` decomposition into the canonical batch/bundle/bin representation and genealogy backfill from TrackingRecords including archived `arch_*` orders); the Plant B OFBiz backfill (parties, products, inventory balances, open production runs) with a recorded genealogy trace-boundary date; a legacy read-only period followed by archival; archival of Qcadoo build artefacts and `nexus.qcadoo.org` snapshot dependencies; and the decommission evidence pack.

**Out of scope for W4** (scope fences from earlier waves — all target functionality must already exist):

- Any new MES functionality: state machine/gating (W1), genealogy/blocking/QI/CoA/ISA-88/hazmat (W2), planning/boundary/SCADA (W3). W4 builds runbooks, migrations, and evidence — not features.
- Master-data migration tooling and round-trip fixtures — built in W0 (W0-5); W4 *uses* that tooling for backfills.
- The migration of Plant C's live ERPNext transactional configuration beyond the journey cutover itself (Plant C moves instance, not data model — its data is anchor-native).

## 2. Personas in scope

All six programme personas are in scope — the wave exit is "all personas on target" (dossier-derived role model: ch. 3.1 §B.2 for Plant A roles; ch. 3.2 for Plant C roles; ch. 3.3 §B for Plant B's undifferentiated model):

| Persona | Fixture name | W4 relevance |
|---|---|---|
| planner | P. Krüger | Signs off planning journey per plant at cutover |
| shop-floor operator | O. Weber | Signs off execution journey; first-day-on-target support |
| quality inspector | Q. Fischer | Signs off QI/blocking journey; verifies migrated qa_states |
| warehouse clerk | W. Braun | Verifies migrated stock (counts, pallets, locations) |
| technologist | T. Schmid | Verifies migrated recipes/gov_state mapping |
| business viewer | B. Vogel | Reads cutover progress and reconciliation dashboards |

## 3. Requirements

IDs `URS-W4-NNN`. Fixed state vocabulary as in the programme glossary: `exec_state` {Pending, Accepted, In Progress, Completed, Interrupted, Abandoned, Declined}; `gov_state` {Draft, Checked, Accepted, Outdated, Declined}; `qa_state` {Quarantined, Released, Blocked}. Never unqualified "status".

### 3.1 Capability area: Cutover execution (backlog W4-1, W4-5)

#### URS-W4-001 — Per-plant, per-journey cutover runbooks
**Statement:** The programme shall produce an executable cutover runbook per plant (Plant A Qcadoo, Plant B OFBiz, Plant C legacy ERPNext instance), structured by the six dossier journeys (define & approve a recipe; plan an order; release to shop floor; execute & record; trace a defect batch; quality disposition), each step with owner, precondition, verification, and abort path.
**Priority:** Must
**Lineage:** — (runbooks) · — · dossier §5.3 journey comparison (the six journeys and their per-system shapes); backlog W4-1; open question §8.2 #7 (Plant B open WIP at cutover) must be answered as a runbook precondition
**Acceptance criteria:**
- AC-1: Given the three runbooks, When reviewed at readiness gate, Then each covers all six §5.3 journeys and every step has owner, precondition, verification, and abort path — no step lacking any of the four.
- AC-2: Given the Plant B runbook, When its preconditions are checked, Then it includes the answered §8.2 #7 register entry (open production runs / WIP inventory at cutover date) with the actual counted values.
- AC-3: Given a dry-run of the Plant A runbook against a staging environment loaded with the W4-2/W4-4 migration outputs, When executed, Then every verification step passes or the runbook is amended — a runbook is not "final" until a dry-run has passed end-to-end.
**Dependencies:** W1-10, W2-9, W3-3 (journeys must be accepted before runbooks can bind them); URS-W4-002…005.

#### URS-W4-002 — Legacy read-only freeze with retained query access
**Statement:** The system programme shall, per plant at cutover, freeze all legacy write access (revoking write roles / disabling write endpoints) while retaining query access for a defined read-only period, before archival.
**Priority:** Must
**Lineage:** — (wave definition) · — · backlog W4-5 "freeze legacy writes, keep query access; then archive"; Plant A role machinery evidence dossier ch. 3.1 §B.2 (Spring Security roles, `security.properties:25`); Plant B permission model ch. 3.3 §B (`MANUFACTURING_*` permissions)
**Acceptance criteria:**
- AC-1: Given Plant A is cut over, When operator O. Weber attempts to accept an order in legacy Qcadoo, Then the write is refused by the revoked role set, while read/query of the same order still succeeds; the freeze date is recorded in the decommission register.
- AC-2: Given the read-only period for Plant B ends per the runbook, When archival is executed (URS-W4-003), Then no legacy query access remains and the archival date is recorded.
**Dependencies:** URS-W4-001; blocks URS-W4-003.

#### URS-W4-003 — Legacy archival
**Statement:** The programme shall archive each legacy system at the end of its read-only period: a restorable full database export, application source at the pinned commit, and configuration — stored in the programme archive with retention metadata and a documented restore procedure tested once.
**Priority:** Must
**Lineage:** — (wave definition) · — · backlog W4-5; pinned commits per dossier §1 (Chem_mes@81d6bb5, VM_ofbiz-framework@ecf2990, Chem_erpnext@31e7970)
**Acceptance criteria:**
- AC-1: Given the Plant A archive package, When the documented restore procedure is executed once into an isolated environment, Then the Qcadoo instance starts and a known order (the legacy source of PO-2026-0001's characterization fixtures) is queryable read-only.
- AC-2: Given all three archive packages, When the decommission register is reviewed, Then each lists content checksum, pinned commit SHA, archive date, and retention owner.
**Dependencies:** URS-W4-002, URS-W4-004 (Qcadoo build-chain archive precedes decommission).

#### URS-W4-004 — Qcadoo build-artefact and snapshot-dependency archive (early)
**Statement:** The programme shall archive, before decommission and independently of other W4 items (start early), the deployable Qcadoo build artefacts (WAR) and all `nexus.qcadoo.org` snapshot dependencies (framework 1.5-SNAPSHOT, `qcadoo-super-pom`) sufficient to rebuild or redeploy Plant A's MES without external repositories.
**Priority:** Must
**Lineage:** — · — · dossier §7 implication 10 (unreproducible build chain — "archive the artefacts early"); ch. 3.1 §D/§E (`pom.xml` snapshot deps resolved from `nexus.qcadoo.org`); backlog W4-6
**Acceptance criteria:**
- AC-1: Given the archived Maven repository mirror and WAR, When a build is executed in a network-isolated environment (no access to nexus.qcadoo.org), Then the Plant A WAR builds (or the archived WAR deploys) successfully — proving independence from the third-party Nexus.
- AC-2: Given the wave plan, When W4 starts, Then this archive task is already scheduled/underway independent of W4-1…W4-5 sequencing (per backlog W4-6 "start early").
**Dependencies:** — (deliberately none; earliest W4 item).

### 3.2 Capability area: Data migration — Plant A (backlog W4-2, W4-4)

#### URS-W4-005 — Plant A stock backfill: Resource decomposition
**Statement:** The migration shall decompose each open lot-level Qcadoo `Resource` row into the canonical representation per CDM-03/ADR-005 — (a) Batch quantity in Bin via opening Stock Ledger Entries and Serial and Batch Bundle allocations, (b) Handling Unit content for pallet numbers, (c) Storage Location assignment, (d) valuation rate — preserving batch, expiry, production date, price, pallet, storage location, `qualityRating` history, and `blockedForQualityControl` (→ `qa_state` per CDM-01 mapping).
**Priority:** Must
**Lineage:** Absorb migration · Qcadoo · dossier ch. 3.1 `ResourceFields.java:32-90` (lot model fields); §7 implication 4 ("data-model migration, not a data copy"); CDM-03 mapping ("decomposed at migration into (Batch qty in Bin) + (Handling Unit content) + (Storage Location assignment) + (valuation rate)"); CDM-01 `qa_state` mapping (`blockedForQualityControl`→Quarantined, `BatchState` BLOCKED→Blocked, TRACKED→Released)
**Source→canonical mapping reference:** CDM-03 (§"Mapping"), CDM-01 (§"Source mapping" rows `batch_id`, `qa_state`, `expiry_date`).
**Acceptance criteria:**
- AC-1: Given a legacy Resource row for RW-CHM-0001, batch string "BATCH-A-0001", 500 kg, expiry 31.12.2026, pallet HU-000123, storage location NORD-A-01-01, price 2.10 €/kg, in warehouse RM Lager Nord, When migrated, Then the target holds: Batch BATCH-A-0001 (`qa_state` Released, expiry 31.12.2026), Bin/SLE on-hand 500 kg in RM Lager Nord at rate 2.10, Handling Unit HU-000123 containing 500 kg of BATCH-A-0001, and Storage Location assignment NORD-A-01-01.
- AC-2: Given a legacy Resource with `blockedForQualityControl` = true for BATCH-A-0002 (Additiv K7, 50 kg, expiry 30.06.2026), When migrated, Then the target Batch BATCH-A-0002 has `qa_state` = Blocked-or-Quarantined exactly per the CDM-01 mapping table (resource flag → Quarantined; genealogy `BatchState` BLOCKED → Blocked), and its stock is excluded from picking availability.
- AC-3: Given RM Lager Nord's legacy disposal algorithm FEFO, When post-migration picking for RW-CHM-0001 runs, Then BATCH-A-0002 (expiry 30.06.2026, if Released) would be offered before BATCH-A-0001 (31.12.2026) — FEFO ordering preserved (`WarehouseAlgorithm.java:26-27` semantics via W1-5).
**Reconciliation criteria:** (i) record counts: migrated Batch count = distinct legacy (batch, product) pairs; Handling Unit count = distinct legacy pallet numbers; (ii) **sum equivalence per warehouse**: Σ target on-hand qty and Σ (qty × rate) value per warehouse = legacy Resource sums per warehouse, exact to 3 decimals, in the per-warehouse reconciliation report required by ADR-005; (iii) spot checks: ≥ 50 randomly sampled Resource rows verified field-by-field (batch, expiry, pallet, location, price), zero tolerated mismatches.
**Rollback condition:** any warehouse failing sum equivalence, or any spot-check mismatch, aborts the plant cutover; migrated target data for Plant A stock is reversed via the migration run ID (all writes tagged), legacy remains writable, and the runbook returns to its pre-migration checkpoint.
**Dependencies:** W0-5 (tooling), W1-5 (HU/Storage Location DocTypes), W2-2 scope (unified batch — cross-wave, parent to reconcile).

#### URS-W4-006 — Plant A genealogy backfill from TrackingRecords including `arch_*`
**Statement:** The migration shall backfill genealogy links (CDM-01 `genealogy_links`) from Qcadoo TrackingRecords (produced batch ↔ used batches) including records attached to archived orders in the `arch_*` shadow tables, merging Qcadoo's dual batch model (genealogy `Batch` + `Resource.batch` strings) per ADR-003; unmatched resource-batch strings shall create identity-only Batches flagged `genealogy_incomplete`.
**Priority:** Must
**Lineage:** Absorb migration · Qcadoo · dossier ch. 3.1 `TrackingRecordFields.java:31-49` (producedBatch/usedBatchesSimple), `mes_db_en.sql:292-648` (archiving machinery `archive`, `archive_connected_orders`, `generate_arch_tables`); ADR-003 consequences; open question §8.2 #2 (genealogy population completeness) must be answered before W4 exit (cross-wave rule 3)
**Source→canonical mapping reference:** CDM-01 §"Source mapping" row `genealogy_links` ("= TrackingRecord used/produced tree"); §"Semantic-mismatch note" (dual-model merge).
**Acceptance criteria:**
- AC-1: Given a legacy TrackingRecord linking produced batch BATCH-C-1001 (500 kg RW-CHM-0003, order matching PO-2026-0001's fixture) to used batches BATCH-A-0001 (400 kg) and BATCH-A-0002 (20 kg), When migrated, Then BATCH-C-1001's `genealogy_links` contain both consumed links with quantities, and the Trace Ribbon for BATCH-C-1001 shows both upstream batches.
- AC-2: Given a TrackingRecord that exists only in `arch_*` tables (archived order), When migration runs, Then its genealogy links are backfilled identically to live-table records — archived history is not dropped.
- AC-3: Given a Resource batch string with no matching genealogy Batch, When migrated, Then an identity-only Batch is created flagged `genealogy_incomplete`, and the count of such batches appears in the reconciliation report.
**Reconciliation criteria:** (i) record counts: target genealogy link count = legacy TrackingRecord used-batch link count (live + `arch_*`), reported separately per source table class; (ii) spot checks: ≥ 25 sampled genealogy trees (incl. ≥ 5 from `arch_*`) compared node-by-node against the legacy `producedFrom`/`usedToProduce` tree browse; (iii) `genealogy_incomplete` count reported and accepted by the quality inspector persona at sign-off.
**Rollback condition:** live-vs-`arch_*` count mismatch beyond the reconciled expected delta, or any spot-check tree mismatch, reverses the genealogy backfill by migration run ID; batch identity data (URS-W4-005) may stand if independently reconciled.
**Dependencies:** W0-5, W2-1 scope (genealogy object model — cross-wave); §8.2 #2 answered.

### 3.3 Capability area: Data migration — Plant B (backlog W4-3)

#### URS-W4-007 — Plant B OFBiz backfill: parties, products, balances, open runs
**Statement:** The migration shall backfill from OFBiz: product master data deltas, party (supplier/customer) references consistent with the D5 boundary decision, inventory balances as opening Stock Ledger Entries per facility/lot (CDM-03), and open production runs mapped to canonical production orders via the fixed CDM-02 status table (`PRUN_CREATED`/`PRUN_SCHEDULED`→Pending, `PRUN_DOC_PRINTED`→Accepted, `PRUN_RUNNING`→In Progress, `PRUN_COMPLETED`/`PRUN_CLOSED`→Completed, `PRUN_CANCELLED`→Abandoned).
**Priority:** Must
**Lineage:** Retire OFBiz · — (data source only, dossier §6.2 "Anything from OFBiz: None … data-migration source only") · dossier ch. 3.3 `product-entitymodel.xml:1967` (`InventoryItem.lotId` optional), `:2419` (`Lot` entity), `WorkEffortSeedData.xml:160-177` (`PRUN_*` states); CDM-02 §"Mapping" (OFBiz open-run status map); CDM-03 §"Mapping" ("OFBiz `InventoryItem(Detail)` ≈ opening-balance SLEs per facility/lot"); open question §8.2 #7 (open WIP) is a precondition
**Source→canonical mapping reference:** CDM-02 §"Mapping" (OFBiz row), CDM-03 §"Mapping" (OFBiz row), CDM-01 §"Source mapping" rows `batch_id` (`Lot.lotId`), `expiry_date` (`Lot.expirationDate`), `qa_state` (∅ → default Released with trace boundary noted).
**Acceptance criteria:**
- AC-1: Given an OFBiz `InventoryItem` of RW-CHM-0002 with `lotId` "B-K7-0009", qty 50 kg, expiry 30.06.2026 in the Plant B facility, When migrated, Then an opening SLE of 50 kg exists in the mapped warehouse against Batch B-K7-0009 (`qa_state` Released per CDM-01 OFBiz default) with expiry 30.06.2026 and `legacy_refs` recording system=OFBiz, ref=B-K7-0009.
- AC-2: Given an OFBiz production run in `PRUN_RUNNING` for RW-CHM-0003, When migrated, Then a canonical production order exists in `exec_state` In Progress with `legacy_refs` to the WorkEffort id — and no other `PRUN_*` value maps to In Progress except `PRUN_RUNNING`.
- AC-3: Given an `InventoryItem` with NULL `lotId`, When migrated, Then its quantity lands as an opening SLE without batch allocation, counted in the no-lot bucket of the reconciliation report (feeds URS-W4-008).
**Reconciliation criteria:** (i) record counts: opening SLE count = migrated `InventoryItem` rows with qty ≠ 0; open-order count per `exec_state` = legacy count per mapped `PRUN_*` state; (ii) sum equivalence per facility/warehouse: Σ migrated qty per (product, warehouse) = legacy QOH per (product, facility), exact; (iii) spot checks: ≥ 30 sampled inventory items and all (100%) open production runs verified field-by-field.
**Rollback condition:** any facility failing sum equivalence or any open-run state mis-mapping reverses the Plant B backfill by migration run ID; Plant B cutover halts and legacy write freeze (URS-W4-002) is lifted for Plant B.
**Dependencies:** W0-5, W2-2 scope, URS-W4-001 (runbook), D5 decision; §8.2 #3 and #7 answered.

#### URS-W4-008 — Plant B genealogy trace-boundary register
**Statement:** The programme shall record a genealogy trace-boundary date for Plant B — the date before which backfilled genealogy is known-incomplete because OFBiz lot tracking was optional — publish it in the trace-boundary register, and the system shall disclose the boundary on trace views of affected batches.
**Priority:** Must
**Lineage:** Retire OFBiz · — · dossier §7 implication 9 ("Plant B's optional-lot history means backfilled genealogy for pre-cutover stock will be incomplete; the trace boundary date must be recorded and communicated"); ch. 3.3 (`Lot` optional on `InventoryItem.lotId`, `product-entitymodel.xml:1967`); open question §8.2 #3 (lot coverage proportion)
**Acceptance criteria:**
- AC-1: Given the answered §8.2 #3 lot-coverage measurement, When the trace-boundary register is published, Then it states the Plant B boundary date, the measured lot-coverage percentage, and the no-lot quantity bucket from URS-W4-007 AC-3.
- AC-2: Given a migrated Plant B batch whose history predates the boundary, When Q. Fischer opens its Trace Ribbon, Then the upstream direction shows an explicit trace-boundary marker (a hard visual break with label naming the register entry) rather than an empty tree presented as complete.
**Design conformance:** The boundary marker follows the Trace Ribbon rules — a hard visual break, printable, identical in CoA and recall views (design skill §"Layout patterns" 4); the disclosure is never hidden behind progressive disclosure (§"Anti-patterns").
**Dependencies:** URS-W4-007; §8.2 #3 answered.

### 3.4 Capability area: Decommission evidence (backlog W4-7)

#### URS-W4-009 — Per-plant persona sign-off
**Statement:** The programme shall obtain and record, per plant, a named sign-off from each in-scope persona confirming their journeys work on the target (the six §5.3 journeys mapped to personas), collected after an agreed on-target operating period.
**Priority:** Must
**Lineage:** — (wave exit) · — · backlog W4-7 "per-plant persona sign-off"; wave exit "all personas on target"; persona model dossier ch. 3.1 §B.2 / ch. 3.2 / ch. 3.3 §B
**Acceptance criteria:**
- AC-1: Given Plant A operates on target, When the sign-off matrix is compiled, Then it contains dated, named entries for P. Krüger (plan an order), O. Weber (release + execute & record), Q. Fischer (trace a defect batch + quality disposition), W. Braun (stock journeys), T. Schmid (define & approve a recipe), B. Vogel (business views) — 6/6 personas, no journey unsigned.
- AC-2: Given any persona withholds sign-off, When the register is reviewed, Then the blocking issue is logged as a named defect with owner — sign-off cannot be recorded "with exceptions" silently.
**Dependencies:** URS-W4-001…008.

#### URS-W4-010 — Decommission evidence pack
**Statement:** The programme shall assemble a decommission evidence pack per plant containing: the executed runbook with verification results, all data-reconciliation reports (URS-W4-005/006/007), the trace-boundary register (URS-W4-008), persona sign-offs (URS-W4-009), freeze/archival dates and archive checksums (URS-W4-002/003/004) — and the pack closes the wave Epic.
**Priority:** Must
**Lineage:** — (wave exit) · — · backlog W4-7 "decommission evidence pack: per-plant persona sign-off, data-reconciliation reports, trace-boundary register"; evidence-pack generator from W0-7
**Acceptance criteria:**
- AC-1: Given the Plant B pack, When audited against the checklist, Then all six artefact classes above are present, each cross-linked to its source record; a pack missing any artefact class cannot be marked complete.
- AC-2: Given all three plant packs complete, When milestone M4 is assessed, Then the M4 criterion ("all personas on target; legacy systems read-only then archived; decommission evidence pack signed off") evaluates true from pack contents alone.
**Dependencies:** URS-W4-002…009; W0-7.

#### URS-W4-011 — Legacy-bridge affordance retirement by feature flag
**Statement:** The system shall retire the legacy-bridge affordance (old-name-on-hover for legacy-mapped fields, e.g. "was: Technology → now: Recipe") per plant after that plant's sign-off, via feature flag — without a code release.
**Priority:** Could
**Lineage:** Design skill §"Interaction rules — Legacy bridge affordance" ("Removable by feature flag after cutover; invaluable during it"); disposition — (UI programme rule, no legacy source)
**Acceptance criteria:**
- AC-1: Given Plant A's sign-off is complete, When the Plant A bridge flag is switched off, Then hovering a migrated field (e.g. Recipe reference on PO-2026-0001) no longer shows "was: Technology → now: Recipe" for Plant A users, while Plant B users (not yet signed off) still see their bridge labels.
**Design conformance:** Flag change causes no layout shift — position stability per design skill §"Anti-patterns" ("unannounced layout changes between releases").
**Dependencies:** URS-W4-009.

### 3.5 Untraceable / deferred

- **Read-only period duration and archive retention periods** — no legacy evidence or ADR sets these; they are business/records-management decisions to be fixed in the runbooks (URS-W4-001) with sign-off. Flagged rather than invented.
- **Plant C legacy-instance data delta** — the dossier treats Plant C data as anchor-native (fork delta "rebrand commits only", §2.3/A1); if cutover discovers site-level Custom Fields/Property Setters in the live instance (not in source), a supplementary mapping requirement must be raised. **Business sign-off required** on the assumption before Plant C cutover.

## 4. Non-functional requirements

#### URS-W4-012 — Migration window performance and resumability
**Statement:** Each plant's data backfill shall complete within the runbook's agreed cutover window, shall be idempotently resumable from the last committed checkpoint after interruption, and every write shall carry the migration run ID enabling the URS-W4-005/006/007 rollbacks.
**Priority:** Must
**Lineage:** §7 implication 4 (migration complexity) · rollback machinery required by ADR-005 reconciliation discipline; window is a runbook parameter (URS-W4-001)
**Acceptance criteria:**
- AC-1: Given the Plant A staging dry-run (URS-W4-001 AC-3) at production data volume, When timed, Then total backfill duration ≤ the runbook window with ≥ 20% headroom.
- AC-2: Given a migration run interrupted mid-warehouse, When resumed, Then it continues from the last checkpoint producing byte-identical reconciliation results to an uninterrupted run (verified by comparing reconciliation reports).

#### URS-W4-013 — Audit of migration and decommission actions
**Statement:** The system shall write immutable audit records for every migration run (run ID, operator, source extract checksums, start/end, record counts, reconciliation outcome) and every freeze/unfreeze/archival action (actor, timestamp, plant, scope).
**Priority:** Must
**Lineage:** Absorb · Qcadoo audit discipline (dossier ch. 3.1 §E state-change audit) extended to programme actions; evidence-pack dependency (URS-W4-010 needs these records)
**Acceptance criteria:**
- AC-1: Given the Plant B backfill run, When the audit log is queried by its run ID, Then operator, checksums, counts, and reconciliation outcome are present and the entry is immutable (no update path exists).
- AC-2: Given URS-W4-002 AC-1's freeze, When audited, Then the freeze entry names the actor, plant (A), timestamp, and revoked scope.

#### URS-W4-014 — Access control for migration and freeze operations
**Statement:** Migration execution, rollback, freeze/unfreeze, and archival shall each require a dedicated migration-operator permission (workflow-level, not general admin), denied by default to all six business personas.
**Priority:** Must
**Lineage:** Absorb · Qcadoo per-action role granularity (dossier ch. 3.1 §B.2, e.g. `ROLE_ARCHIVING` as a distinct role; implication 7) on the W1-8 role model
**Acceptance criteria:**
- AC-1: Given P. Krüger's planner role set, When P. Krüger attempts to trigger a migration rollback, Then it is refused and audited; When the designated migration operator triggers it, Then it succeeds with audit per URS-W4-013.
**Dependencies:** W1-8.

## 5. Data migration requirements

W4 is the migration-heavy wave; the full data-migration requirements are first-class URS items above rather than a separate annex:

| Migration | URS | Source→canonical mapping | Reconciliation | Rollback |
|---|---|---|---|---|
| Plant A stock (Resource decomposition) | URS-W4-005 | CDM-03 mapping; CDM-01 `qa_state`/`expiry` rows | counts + per-warehouse sum equivalence (qty and value) + ≥50 spot checks | sum/spot failure → reverse by run ID, cutover abort |
| Plant A genealogy (TrackingRecords incl. `arch_*`) | URS-W4-006 | CDM-01 `genealogy_links` row; ADR-003 dual-model merge | link counts (live vs `arch_*`) + ≥25 tree spot checks + `genealogy_incomplete` count | count/tree mismatch → reverse genealogy by run ID |
| Plant B (parties/products/balances/open runs) | URS-W4-007 | CDM-02 OFBiz status map; CDM-03 OFBiz row; CDM-01 OFBiz rows | counts + per-facility sum equivalence + 100% open runs + ≥30 items | sum/state-map failure → reverse by run ID, lift freeze |
| Plant B trace boundary | URS-W4-008 | CDM-01 `qa_state` OFBiz "∅ (default Released; trace-boundary noted)" | register completeness vs §8.2 #3 measurement | n/a (register, not data write) |

Master-data backfills reuse the W0-5 extractors and round-trip fixtures; W0 migrated master data, W2 migrated open batches/genealogy structures — W4 backfills the remaining transactional history and balances listed above.

## 6. Wave exit criteria

Restated from `docs/40-planning/cutover-decommission/W4-cutover-decommission.md` ("**Exit:** all personas on target; decommission complete") and decomposed:

| ID | Check | Verifies |
|---|---|---|
| EXIT-W4-1 | All three per-plant runbooks executed with every verification step passed (or amended + re-run); §8.2 #2/#3/#7 answered in the programme register beforehand | URS-W4-001 |
| EXIT-W4-2 | All six personas signed off per plant (18 sign-off entries), zero silent exceptions | URS-W4-009 |
| EXIT-W4-3 | All reconciliation reports pass: Plant A per-warehouse sum equivalence + spot checks; Plant A genealogy counts incl. `arch_*`; Plant B per-facility sums + 100% open-run state mapping | URS-W4-005…007, URS-W4-012 |
| EXIT-W4-4 | Trace-boundary register published and surfaced in trace views for affected Plant B batches | URS-W4-008 |
| EXIT-W4-5 | Legacy systems frozen read-only then archived, restore procedure tested once per plant; Qcadoo build-chain archive proven network-isolated | URS-W4-002…004 |
| EXIT-W4-6 | Decommission evidence packs complete for all three plants and M4 evaluates true from pack contents | URS-W4-010, URS-W4-013 |
