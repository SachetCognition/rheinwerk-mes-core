# W2 migration — open batches, genealogy history and legacy quality flags

**URS:** URS-W2-030, URS-W2-031, URS-W2-032 (`docs/urs/URS-W2-traceability-quality.md` §3.10)
**Tests:** TC-W2-042…045 (`docs/test/TST-W2-traceability-quality.md`)
**Mappings:** CDM-01, CDM-07 (`docs/canonical-model/README.md`)
**Package:** `rheinwerk_mes/integration/migration/w2/`

This migration carries the *open* (not-yet-closed) production world of the three pilot
plants onto the canonical ERPNext `Batch` delivered by the W2 genealogy child: open batch
identity, historical genealogy edges, and the legacy quality dispositions. It **extends**
the W0-5 three-source migration framework (`rheinwerk_mes/integration/migration/`) — the
reversible run journal, the deterministic spot-check sampler and the German-first report
style — rather than starting a second system, and it writes only through the canonical
`Batch` / `qa_state` / genealogy-link surfaces owned by `rheinwerk_mes/genealogy/`.

## 1. Staging / extraction model

Extraction is **offline and site-free** (`w2/extract.py` → `w2/model.py`), mirroring the
W0-5 `canonical.CanonicalExtract` split. Each source fixture under
`integration/migration/fixtures/w2/` is read into one dialect-neutral `W2Extract`
(`StagedBatch` + `StagedLink`), so the dual-model merge, the tracking-tree fold and the
flag→state map are deterministic and unit-testable without a database. The loaders,
reconcilers and rollback then never learn a source dialect.

Legacy shapes are **re-expressed, never ported** (semantics only):

| Source | Read | Re-expressed as |
|---|---|---|
| Qcadoo (`Chem_mes@master`) | `advancedgenealogy` `Batch.number` + `BatchState`, `materialflowresources` `Resource.batch` / `expirationDate` / `blockedForQualityControl` / `qualityRating`, `TrackingRecord` used/produced trees | merged canonical `Batch`, `qa_state`, genealogy links |
| OFBiz (`VM_ofbiz-framework@trunk`) | `Lot`, `WorkEffortInventoryAssign` / `WorkEffortInventoryProduced` (`lotId` presence) | canonical `Batch`, genealogy links, trace boundary |
| ERPNext legacy | anchor `Batch` (+ `disabled`), production history | canonical `Batch`, genealogy links |

### Dual-model merge (URS-W2-030)

Qcadoo keeps batch identity in *two* places. The extractor forms the union of genealogy
`Batch.number` and warehouse `Resource.batch` strings:

* **matched pair** (a genealogy batch *and* a resource string of the same number) → **one**
  canonical `Batch` carrying **both** `legacy_refs` (`advancedgenealogy_batch` +
  `materialflowresources_resource`), `genealogy_incomplete = false`;
* **unmatched resource string** → an **identity-only** canonical `Batch` with only the
  resource `legacy_ref`, flagged `genealogy_incomplete = true`.

`BatchState` maps `TRACKED → Released`, `BLOCKED → Blocked`; `blockedForQualityControl`
maps `→ Quarantined` (and dominates the disposition). When several resource lots merge into
one batch the **earliest** `expirationDate` wins and the divergence is reported as an
expiry conflict (German-first, DD.MM.YYYY).

### Trace boundary (URS-W2-031)

OFBiz Plant B history is only as traceable as its `lotId`s. A produced lot whose consumed
input row has **no `lotId`** cannot be fully traced back; that produced batch is flagged
`genealogy_incomplete` and stamped with the **plant-wide** OFBiz `trace_boundary_date`, so
the trace terminates explicitly rather than silently dropping an edge.

## 2. Load steps (three independently-reversible runs)

`w2/loaders.py` runs three steps, **each with its own `run_id` and its own journal** (the
W0-5 `JournalEntry` / `write_journal` format), which is what gives the documented retention
semantics:

1. **`load_batches`** (URS-W2-030) — insert/update canonical `Batch` identity: `batch_id`,
   `item`, earliest `expiry_date`, `qty_original`, `supplier_batch_no`, both `legacy_refs`,
   and `genealogy_incomplete` for orphan resource strings. Disposition is left at the
   `Quarantined` entry default.
2. **`load_links`** (URS-W2-031) — fold the used/produced trees onto each produced `Batch`
   as `genealogy_links` child rows (one `produced` self-edge + n `consumed` edges,
   quantities preserved 1:1), and stamp the Plant B trace-boundary flag/date.
3. **`load_state`** (URS-W2-030 mapping / URS-W2-032 history) — assign `qa_state` and, for
   flag-derived Quarantined/Blocked batches, append a `qa_state_history` row naming the
   legacy flag as the origin.

### Run IDs and journal ownership

Run ids are `w2<step>-<plant>-<utc-timestamp>` via `importer.new_run_id`. Each journal
lives at `<site>/private/files/rheinwerk_mes_migration/<run_id>.json` and records, per
touched document, whether the step inserted it or updated it and — for updates — a
**W2-aware snapshot** of the exact scalar fields *and* child-table rows that step changed
(`_w2` marker). A step's journal therefore describes *only* that step's delta.

## 3. Rollback and retention semantics

`w2/rollback.py` replays one journal backwards (`rollback_run(run_id)`), extending the W0-5
rollback so it also reverts child tables (`genealogy_links`, `qa_state_history`) and
restores `qa_state` at the **db level** (a legacy bulk load legitimately reproduces reverse
edges the interactive state machine forbids). Because each step owns its own journal:

* rolling back **links** removes the `genealogy_links` rows and the trace-boundary flag but
  **keeps** the batches URS-W2-030 created (TC-W2-044);
* rolling back **state** reverts `qa_state` / `qa_state_history` only;
* rolling back **batches** deletes exactly the batches that step inserted (TC-W2-043).

A whole-run teardown (`cli.rollback_plant`) orders the steps **links → state → batches** so
a produced batch's links are gone before the batch itself is deleted (link integrity).

## 4. Reconciliation artefacts

`w2/reconcile.py` reads the target site and compares it to the staging extract (staging is
derived purely from committed fixtures, so target-vs-staging *is* target-vs-legacy),
emitting a German-first PASS/FAIL report — the citable pilot artefact written by
`cli.run_w2_migration` to `.../rheinwerk_mes_migration/w2-pilot-reconciliation.md`. Criteria
implemented as code:

* per-plant batch counts, `(batch_id, item, expiry_date)` SHA-256 checksum, and a
  deterministic identity spot-check (URS asks 100 records; the pilot subset is smaller so
  the sample is every record — a strict superset);
* `qa_state` distribution and Quarantined/Blocked counts vs the legacy flags;
* genealogy link counts by direction, a **zero-orphan** check, and a backward-trace
  spot-check (URS asks 50 trees; again every tree on the pilot subset);
* Plant B trace-boundary date recorded;
* **global**: zero `Quality Inspection` records before the migration cut date (`2026-01-01`).

On a reconciliation FAIL `run_w2_migration` rolls the run back by run id (unless
`keep_on_fail`), per the URS rollback conditions.

## 5. Legacy quality flags as history only (URS-W2-032)

`qualityRating` / `blockedForQualityControl` (Qcadoo) and `quantityRejected` (OFBiz) migrate
**only** as `qa_state` + `qa_state_history` notes. The migration creates **no** parametric
`Quality Inspection` record, and the reconciliation asserts none predates the cut date.

## 6. Ambiguity decisions (ADR notes)

* **Historical genealogy is written as `genealogy_link` child rows directly on the produced
  `Batch`.** The genealogy module's `links.rebuild_links_for_work_order` derives links from
  *submitted Stock Entries*; a historical migration has no Stock Entries, so that entrypoint
  is inadequate for a bulk load. We therefore append `genealogy_links` rows through the
  module's own field/direction constants (`links.LINK_FIELD`, `consumed`/`produced`) and
  read them back exclusively through `links.links_of` / `trace.backward`. **Recommendation:**
  a future `links.load_historical(...)` entrypoint in the genealogy module.
* **State assignment bypasses the interactive `qa_state.transition` machine.** That machine
  gates live reasons/roles, forbids the `Quarantined → Quarantined` entry note AC-1 needs,
  and refuses reverse edges a legacy load reproduces. `load_state` sets `qa_state` at the db
  level and writes the audit `qa_state_history` row itself, citing the legacy origin — the
  disposition is a *historical fact*, not a live transition.
* **The `qa_state` vocabulary is duplicated as module-level constants** in `w2/model.py`
  (which must stay import-safe offline) and asserted equal to
  `genealogy.qa_state.{QUARANTINED,RELEASED,BLOCKED}` in the acceptance suite.
* **Earliest expiry wins** on a merged batch; the conflict is reported, not hidden.

## 7. Entry points

```bash
# full pilot: load A/B/C, reconcile, write the report artefact (rolls back on FAIL)
bench --site dev.localhost execute rheinwerk_mes.integration.migration.w2.cli.run_w2_migration
# reverse a single step by run id
bench --site dev.localhost execute rheinwerk_mes.integration.migration.w2.cli.rollback_step --args "['<run_id>']"
```

The published W0-5 `cli.run_all` signature is untouched — W2 is purely additive.
