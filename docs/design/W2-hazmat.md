# W2-7 — Hazmat / regulatory master data (`regulatory_hazmat`)

Design note for backlog item **W2-7** (URS-W2-023, URS-W2-024), module track
`regulatory_hazmat`. It documents the hazmat data model layered onto the anchor `Item` and
anchor `Batch` *without forking either*, the validation and audit rules, how hazmat becomes
visible in warehouse and trace surfaces, and — explicitly — **what W3 still owes**, because
W2-7 only *starts* this capability (CONSOLIDATION.md: `regulatory_hazmat` completes in W3).

This capability is **white space in all three legacy systems** (dossier §6.3, ch. G
"Hazmat: Absent" ×3 with documented searches): there is no Qcadoo behaviour to absorb, no
OFBiz data to migrate and therefore **no parity contract and no characterisation test**. The
model is designed from the URS and from German chemical-industry regulation, which is the
only authority available:

| Concern | Authority | Where it lives |
|---|---|---|
| UN/ADR number | UN Recommendations on the Transport of Dangerous Goods / ADR — exactly four digits, rendered `UN NNNN` | `contracts.normalise_un_number` |
| Lagerklasse (storage class) | **TRGS 510** Anlage 1 (Lagerung von Gefahrstoffen in ortsbeweglichen Behältern) — closed class list 1 … 13 | `contracts.STORAGE_CLASSES` |
| Signal word, pictograms, H/EUH/P statements | **CLP**, Regulation (EC) 1272/2008 (Anhang V for GHS01…GHS09) | `contracts.GHS_PICTOGRAMS`, `contracts.validate_statement_code` |
| Wassergefährdungsklasse (WGK) | **AwSV** — 1, 2, 3, `nwg` | `contracts.WATER_HAZARD_CLASSES` |
| Safety data sheet (SDB/SDS) reference + version | REACH Art. 31 / (EU) 2020/878 | `Hazmat Profile.sds_*` |

Related: `docs/design/W2-genealogy.md` (the canonical `Batch` and the Trace Ribbon model this
decorates), `docs/canonical-model/README.md` (CDM-01 `hazmat_profile`),
`docs/urs/URS-W2-traceability-quality.md` §3.7, `docs/test/TST-W2-traceability-quality.md`
(TC-W2-031, TC-W2-032), `rheinwerk-mes-design-SKILL.md` (signal/density rules).

## 1. What "no anchor fork" means here

The regulatory record is app-owned; the anchors only *point at it*:

```
 Hazmat Profile (rheinwerk_mes, module Regulatory Hazmat)      ← all regulatory data
   ├─ pictograms : Hazmat Pictogram[]        (GHS01…GHS09 + German designation)
   ├─ statements : Hazmat Statement[]        (H/EUH/P code + text)
   └─ revisions  : Hazmat Profile Revision[] (field, before, after, user, timestamp)
        ▲                        ▲
        │ Link                   │ Link (override, only for repacked goods)
   Item (anchor)  ──has batches──  Batch (anchor)
     rw_hazmat_profile              rw_hazmat_profile
     rw_hazmat_mandatory            rw_hazmat_un_number      (read-only mirror)
                                    rw_hazmat_storage_class  (read-only mirror)
```

The only anchor-side artefacts are five **Custom Fields** (plus their section breaks) in the
`Regulatory Hazmat` module, created idempotently by the committed installer
`rheinwerk_mes/setup/w2_hazmat.py` (run from `after_install` and from the `patches.txt`
entry). `Item` and `Batch` keep their `erpnext` schema unchanged — asserted by
`test_tc_w2_031_anchors_are_not_forked` alongside the standing TC-W0-007 anchor-fork guard.

## 2. Field model

### 2.1 `Hazmat Profile`

| Field | Type | Rule |
|---|---|---|
| `profile_name` | Data (name) | unique; the fixture convention is `HAZ-<item>` |
| `un_number` | Data | normalised to `UN NNNN`; four digits or the save is refused |
| `proper_shipping_name` | Data | ADR "ordentliche technische Benennung", German |
| `storage_class` | Select | TRGS 510 class list; free text is impossible by construction |
| `storage_class_designation` | Read-only Data | derived German designation, so no screen ever shows a bare code |
| `water_hazard_class` | Select | AwSV `1` / `2` / `3` / `nwg` |
| `signal_word` | Select | CLP `Gefahr` / `Achtung` |
| `pictograms` | Table | `GHS01…GHS09`; designation derived |
| `statements` | Table | `H…`/`EUH…` under `statement_type = H`, `P…` under `P`; shape-validated |
| `sds_reference`, `sds_version`, `sds_revision_date`, `sds_attachment` | Data / Data / Date / Attach | the safety-data-sheet pointer URS-W2-023 names |
| `revision` | Read-only Int | bumped on every audited change, starts at 1 |
| `revisions` | Table | the audit trail (§3.3) |

### 2.2 Anchor Custom Fields

| Anchor | Field | Purpose |
|---|---|---|
| `Item` | `rw_hazmat_profile` (Link) | the item's hazmat master data (URS-W2-023 AC-1) |
| `Item` | `rw_hazmat_mandatory` (Check) | hazmat-mandatory flag; gates batch creation (AC-2) |
| `Batch` | `rw_hazmat_profile` (Link) | batch-level override, **only** for repacked/re-drummed goods (AC-1) |
| `Batch` | `rw_hazmat_un_number`, `rw_hazmat_storage_class` (read-only Data) | derived mirrors of the effective profile, so hazmat is a *column* in any batch-backed list without a client-side join (URS-W2-024) |

The mirrors are derived data, never a second source of truth: they are recomputed on every
Batch save (`profiles.sync_batch_hazmat_fields`), when an item's profile changes
(`profiles.refresh_item_batches`) and by the installer's `backfill_batch_mirrors()`.

## 3. Rules

### 3.1 Resolution — item profile, batch override

Every surface resolves hazmat through **one** function,
`regulatory_hazmat.profiles.effective_profile(batch=…, item=…)`:

```
effective profile of a batch = batch.rw_hazmat_profile or batch.item.rw_hazmat_profile
```

so an item-level profile is visible on the batch (AC-1 first half) and a repacked batch may
carry its own (AC-1 second half). No caller re-implements the precedence.

### 3.2 The hazmat-mandatory gate

`profiles.enforce_hazmat_profile` runs on `Batch.before_validate` (registered additively in
`hooks.py`). If the item is flagged `rw_hazmat_mandatory` and neither the item nor the batch
resolves a profile, creation is refused with a message that names **rule, record and
resolution** per the design skill:

> Regel: Für Artikel RW-CHM-0001 ist ein Gefahrstoffprofil vorgeschrieben. Datensatz:
> Charge BATCH-A-0004. Abhilfe: Gefahrstoffprofil am Artikel hinterlegen oder an der Charge
> überschreiben (Feld „Gefahrstoffprofil“).

Items *not* flagged mandatory are untouched: a non-hazardous item (RW-CHM-0002 in the
fixtures) creates batches exactly as before, so the gate cannot become an accidental
programme-wide hard stop.

### 3.3 Version audit of regulatory changes

`Hazmat Profile.validate` compares the audited fields against `get_doc_before_save()` and
appends one `Hazmat Profile Revision` row per changed field with **field, value before, value
after, user and timestamp**, bumping `revision` once per save (URS-W2-023 AC-3). Audited:
`un_number`, `storage_class`, `sds_reference`, `sds_version`, `sds_revision_date`,
`water_hazard_class`, `signal_word` — the URS names the SDS reference explicitly, the others
carry the same regulatory weight and would otherwise be silently mutable. The child table is
append-only in practice; nothing in the app deletes rows.

### 3.4 Visibility (URS-W2-024)

Hazmat is a *density* requirement, not a new screen, and both surfaces are produced
**additively** so no sibling package is restructured:

| Surface | API | What renders |
|---|---|---|
| Warehouse stock view | `regulatory_hazmat.views.stock_view(warehouse, item=None)` | one row per batch with positive balance (via `warehouse.availability.ledger_balance`), with `hazmat_un_number`, `hazmat_storage_class`, `hazmat_storage_class_label` as **columns** plus the chip |
| Trace Ribbon | `regulatory_hazmat.views.ribbon(batch, levels=None)` | the W2-1 model from `genealogy.ribbon.ribbon`, decorated: every node gains `hazmat`, `hazmat_un_number`, `hazmat_storage_class` and a hazmat **pill** *in addition to* its `qa_state` pill |
| Item / Batch form | `views.batch_hazmat(batch)` + `public/js/hazmat.js` | one shared chip component (`doctype_js` on the anchors, no fork) |

Signal mapping (`contracts.signal_for_storage_class`), always **icon + label + colour**,
never colour alone:

| Lagerklasse | Signal | Rationale |
|---|---|---|
| 1, 2A, 2B, 3, 4.1A, 4.1B, 4.2, 4.3, 5.1A–C, 5.2, 6.1A, 6.1B, 6.2, 7 | red `--rw-signal-red`, `alert-octagon` | acute hazard — explosive, flammable, oxidising, acutely toxic, radioactive |
| 6.1C, 6.1D, 8A, 8B | amber `--rw-signal-amber`, `alert-triangle` | chronically toxic / corrosive — hazardous, not an acute stop |
| 10, 11, 12, 13 | blue `--rw-signal-blue`, `info` | non-CLP storage classes: informational |

Non-hazardous material yields **no chip at all** (`hazmat: null`), never an empty
placeholder. Nothing hides behind progressive disclosure: the mirrors are
`in_list_view`/`in_standard_filter`, the `Gefahrstoffdaten` sections are not collapsible and
carry no `depends_on` (asserted by TC-W2-032). Dates render DD.MM.YYYY, mass in kg.

### 3.5 Ambiguities resolved (URS §7 / programme rule 7)

1. **Whose profile wins on a batch** — the URS allows a batch override "for repacked goods"
   but does not define precedence. Read as *batch override wins outright* (not "merge"),
   because a repack changes packaging and therefore the transport identity as a whole; a
   partial override would produce an SDS/UN combination that exists in no document.
2. **Scope of the mandatory gate** — enforced per item flag, not globally per storage class,
   so introducing hazmat data cannot retroactively block existing non-hazardous masters.
3. **Which fields are audited** — extended beyond the SDS reference (§3.3).
4. **Where the mirrors live** — on the `Batch` rather than in a report-only join, because the
   URS demands hazmat *columns* in stock views, and W2-8's pallet/location views (a parallel
   track) then get them for free without depending on this module.

## 4. What W2-7 delivers, and what W3 owes

W2-7 delivers **master data + visibility**: the profile record, its regulatory validation and
audit, the anchor links with the mandatory gate, the warehouse/trace decorations, and
fixtures (RW-CHM-0001 → `UN 1866`/`SDS-RW-0001`/Lagerklasse 3, RW-CHM-0003 → `UN 1263`,
both WGK 2, signal word `Gefahr`).

**Deliberately deferred to W3** (URS-W2-023 "boundary/label data explicitly deferred to
W3-6"; CONSOLIDATION.md `regulatory_hazmat` completes in W3):

| Deferred | Why it is not W2 |
|---|---|
| **Shipping / ADR boundary** — transport classification (ADR class, packing group, tunnel code, LQ), consignment documents, the dangerous-goods declaration | W3-6 owns the outbound boundary; W2 has no shipping object to hang it on |
| **GHS labels and printing** — label layout, pictogram artwork, per-package label print with batch data | needs the W3 document/print stack; W2 stores codes, not artwork |
| **Storage-compatibility rules** — TRGS 510 separate-storage matrix (which Lagerklassen may share a storage area) and refusal of an incompatible putaway | needs W2-8 pallet/location balances as its input; the profile data modelled here is the prerequisite |
| **Quantity thresholds** — TRGS 510 small-quantity limits and per-area aggregate ceilings | same dependency as above |
| **SDS distribution** — customer-facing SDS dispatch and revision notification | boundary capability, W3 |
| **Authority reporting** — hazardous-substance register / Gefahrstoffverzeichnis exports | reporting wave |

Nothing in W2-7 pre-empts those: the profile is the single record they will all read, the
audit trail is already field-level, and `views.batch_hazmat` is the entry point W3-6 consumes.

## 5. Traceability

| URS | Requirement | Test |
|---|---|---|
| URS-W2-023 AC-1 | profile linkable from Item/Batch, visible on the batch via its item, batch override for repacked goods | `tests/acceptance/test_w2_hazmat_profile.py::test_tc_w2_031_profile_is_visible_on_the_batch_via_its_item`, `::test_tc_w2_031_batch_level_override_wins_for_repacked_goods` (TC-W2-031 step 1) |
| URS-W2-023 AC-2 | hazmat-mandatory item without profile refuses batch creation | `::test_tc_w2_031_batch_of_a_hazmat_mandatory_item_without_profile_is_refused` (TC-W2-031 step 2) |
| URS-W2-023 AC-3 | SDS reference change version-audited (user, timestamp, before/after) | `::test_tc_w2_031_sds_reference_change_is_version_audited` (TC-W2-031 step 3) |
| URS-W2-023 (rule 1) | no anchor fork | `::test_tc_w2_031_anchors_are_not_forked` |
| URS-W2-024 AC-1 | Lagerklasse + UN number as columns/chips in stock view and Trace Ribbon, not behind disclosure | `tests/acceptance/test_w2_hazmat_visibility.py::test_tc_w2_032_stock_view_carries_hazmat_columns`, `::test_tc_w2_032_trace_ribbon_nodes_carry_the_hazmat_chip`, `::test_tc_w2_032_hazmat_fields_are_not_behind_progressive_disclosure` (TC-W2-032) |
