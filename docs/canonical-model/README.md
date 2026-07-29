# Canonical Data Model v1 (Stage 2.3)

Canonical target entities for every consolidation-critical concept flagged in the dossier's data-model comparison (§5.2), each with fields, semantics, lifecycle, and an explicit field-level mapping from all three source systems — including the same-word/different-meaning mismatches. Each entity is ratified by an ADR (ADR-003 … ADR-010) before any wave touches it.

| ID | Canonical entity | ADR | First wave |
|---|---|---|---|
| CDM-01 | Batch | ADR-003 | W2 (referenced from W0 master data) |
| CDM-02 | Production Order | ADR-004 | W1 |
| CDM-03 | Stock Record (on-hand representation) | ADR-005 | W0 |
| CDM-04 | Recipe (BOM + Routing + governance) | ADR-006 | W1 |
| CDM-05 | Stock Movement | ADR-007 | W1 |
| CDM-06 | Reservation | ADR-008 | W1 |
| CDM-07 | Quality Result | ADR-009 | W2 |
| CDM-08 | Work Centre | ADR-010 | W0 |
| CDM-09 | Item / Product master ([item-master.md](item-master.md)) | — (adopted anchor) | W0 |

Conventions: canonical entities are Frappe DocTypes in the `rheinwerk_mes` app or anchor DocTypes used as-is; anchor DocTypes are never forked — canonical extensions land as linked DocTypes or custom fields. Source mapping legend: **=** direct, **≈** transform, **∅** no source equivalent (backfill/default), **✕** deliberately not carried.

---

## CDM-01 Batch (deliberately designed beyond all three sources)

Traceability is the chemicals-critical capability; all three sources are partial (Qcadoo: stateful genealogy batch *separate from* warehouse lot strings; ERPNext: stateless master data; OFBiz: optional tag). The canonical Batch is the single lot-identity object carrying **identity + QA state + expiry + genealogy** — no source has all four.

**Fields**

| Field | Type | Semantics |
|---|---|---|
| `batch_id` | naming series `BATCH-{plant}-{#}` | Globally unique; legacy ids preserved in `legacy_refs` |
| `item` | Link Item | The material this lot instantiates |
| `qty_original` / `uom` | Float / Link | Quantity at creation |
| `manufacturing_date`, `expiry_date` | Date | Expiry mandatory for shelf-life items; drives FEFO + hard stop |
| `qa_state` | Select: `Quarantined → Released → Blocked` (re-enterable Blocked⇄Released) | Workflow-governed; **not** a boolean |
| `supplier_batch_no` | Data | External lot reference |
| `parent_batch` | Link Batch | Split/repack lineage (distinct from genealogy) |
| `genealogy_links` | child table → Genealogy Link (`direction`: consumed/produced, `batch`, `production_order`, `qty`) | System-of-record trace |
| `hazmat_profile` | Link Hazmat Profile | Chemicals layer (T22) |
| `legacy_refs` | child table (`system`, `ref`) | Qcadoo batch id / resource batch string, ERPNext batch_no, OFBiz lotId |

**Lifecycle:** created Quarantined (or Released where QC-exempt) → Released by Quality Result acceptance (CDM-07) → Blocked/unblocked by QA decision with mandatory reason; Blocked excludes all stock of the batch from picking and reservation and propagates an advisory flag down genealogy.

**Source mapping**

| Canonical field | Qcadoo | ERPNext | OFBiz |
|---|---|---|---|
| `batch_id` | ≈ `advancedGenealogy.Batch.number` **and** `Resource.batch` string (dual model collapsed; conventionally-linked pairs merged at migration) | = `Batch.batch_id` | ≈ `Lot.lotId` |
| `qa_state` | ≈ `BatchState` TRACKED→Released, BLOCKED→Blocked; `Resource.blockedForQualityControl`→Quarantined | ≈ `disabled`→Blocked; else Released (∅ Quarantined — backfill from open QIs) | ∅ (default Released; trace-boundary noted) |
| `expiry_date` | = `Resource.expirationDate` (lot-level → batch-level: earliest wins, conflicts reported) | = `Batch.expiry_date` | = `Lot.expirationDate` |
| `genealogy_links` | = TrackingRecord used/produced tree | ≈ derived from SLE + Serial and Batch Bundle joins | ≈ `WorkEffortInventoryAssign/-Produced` joins where lotId present |
| `parent_batch` | ∅ | = `Batch.parent_batch` | ∅ |
| `supplier_batch_no` | ≈ delivery batch fields | = `Batch.supplier_batch_id` | ∅ |
| `hazmat_profile` | ∅ | ∅ | ∅ (white space) |

**Semantic-mismatch note:** "batch" (Qcadoo genealogy object) ≠ "batch" (Qcadoo resource string) ≠ "Batch" (ERPNext master data) ≠ "Lot" (OFBiz tag). The canonical entity supersedes all four meanings; migration merges Qcadoo's dual model, with unmatched resource-batch strings creating identity-only Batches flagged `genealogy_incomplete`.

---

## CDM-02 Production Order

**Fields:** anchor `Work Order` fields (item, bom, qty, planned dates, warehouses, produced_qty) **plus** integrity-layer extension: `exec_state` (Select: `Pending → Accepted → In Progress → {Completed | Interrupted | Abandoned} ; Pending/Accepted → Declined`), `production_line` (Link), `master_order` (Link, sales aggregation), `state_history` (child table: state, user, timestamp, reason).

**Semantics:** `exec_state` is the user-owned, role-gated workflow (source of truth for shop-floor status); anchor `status` remains the posting-derived reflection — the two are reconciled by hooks (accepting requires anchor submit; completing requires produced ≥ ordered or explicit shortfall reason). Same-word mismatch "status" (dossier §5.2) resolved by *renaming*: canonical never exposes "status" unqualified.

**Mapping:** Qcadoo `Order.state` = `exec_state`; ERPNext `Work Order.status` ≈ derived reflection (unchanged); OFBiz `WorkEffort.currentStatusId` ≈ `PRUN_CREATED/SCHEDULED→Pending`, `DOC_PRINTED→Accepted`, `RUNNING→In Progress`, `COMPLETED/CLOSED→Completed`, `CANCELLED→Abandoned` (migration map for open runs only).

---

## CDM-03 Stock Record (on-hand representation)

**Decision:** the anchor's ledger representation is canonical — immutable `Stock Ledger Entry` stream + `Bin` cache + `Serial and Batch Bundle` allocations. Physical fidelity is layered on with two integrity DocTypes: `Handling Unit` (pallet/load-unit: id, type, current storage location, contents child table) and `Storage Location` (warehouse-scoped tree below the anchor Warehouse).

**Mapping:** Qcadoo lot-level `Resource` rows ≈ decomposed at migration into (Batch qty in Bin) + (Handling Unit content) + (Storage Location assignment) + (valuation rate); price/expiry/pallet/location detail is preserved across the three targets — reconciliation report per warehouse proves sum equivalence. ERPNext SLE/Bin = as-is. OFBiz `InventoryItem(Detail)` ≈ opening-balance SLEs per facility/lot.

**Mismatch note:** "stock on hand" as physical-lot rows (Qcadoo) vs ledger+cache (ERPNext) vs item records (OFBiz) — canonical truth is the ledger; physical detail is *referenced* (HU/location links on bundles), never a parallel quantity store (single-truth constraint, implication 4).

---

## CDM-04 Recipe

**Fields:** anchor `BOM` (materials, operations, costing) + anchor `Routing` (reusable operation sequences) + integrity extension `Recipe Governance` (Link BOM; `gov_state`: `Draft → Checked → Accepted → Outdated`, `Declined` from Draft/Checked; validator results child table; `in_use_lock` flag).

**Semantics:** Accepted recipes are immutable — changes require a new BOM version, the predecessor moves to Outdated; structural validators (tree completeness, UoM consistency, output declaration) run at Checked→Accepted; orders may only reference Accepted recipes (gate in CDM-02 accept).

**Mapping:** Qcadoo `Technology` + TOC tree ≈ BOM(+Routing) explosion, `TechnologyState` = `gov_state` (5-state incl. `checked`); ERPNext `BOM` = base (docstatus/is_active ≈ ∅ governance — backfilled Accepted for active defaults); OFBiz `ProductAssoc MANUF_COMPONENT` + WorkEffort routings ≈ BOM+Routing import, ∅ governance.

**Mismatch note:** Qcadoo unifies BOM+routing in one governed tree; anchor splits them. Canonical keeps the split (anchor-native) and governs the *pair* through `Recipe Governance` covering the BOM and its selected routing together.

---

## CDM-05 Stock Movement

**Decision:** anchor `Stock Entry` (+ purpose types) is canonical; Qcadoo's five `Document` types map onto purposes (Receipt→Material Receipt, Release→Material Issue, Transfer→Material Transfer, internal in/out pairs→Transfer). Acceptance semantics (draft documents reserve, acceptance posts atomically) are carried by CDM-06 reservations + submit hooks, not by a parallel document engine. OFBiz service-written `InventoryItemDetail` rows have no document equivalent → migrated as ledger history only.

---

## CDM-06 Reservation

**Decision:** anchor `Stock Reservation Entry` (batch-capable, 8-state) is canonical. Integrity extension: `draft_reservation` flag replicating Qcadoo "draft makes reservation" (draft stock documents create SREs automatically; deleting/rejecting the draft releases them). Order-level reservations = SREs against Work Order (anchor-native).

**Mapping:** Qcadoo `Reservation` rows ≈ SREs (document-draft origin flagged); ERPNext SRE = as-is; OFBiz `OrderItemShipGrpInvRes` ✕ (sales-order reservations belong to group ERP across the boundary).

---

## CDM-07 Quality Result

**Decision:** anchor `Quality Inspection` (typed, parametric readings, template-driven) is canonical. Chemicals extension: `CoA Certificate` (Link Batch; readings snapshot; approved signatory; issued date; PDF artifact) generated from accepted inspections (T12). Integrity hook: inspection acceptance drives CDM-01 `qa_state` (Quarantined→Released); rejection routes to QA disposition (Blocked or rework).

**Mapping:** ERPNext QI = as-is; Qcadoo `qualityRating`/`blockedForQualityControl` flags ≈ migrated as QA-state history only (no parametric backfill); OFBiz `quantityRejected` ≈ historical note on migrated orders, no QI backfill.

---

## CDM-08 Work Centre

**Decision:** anchor `Workstation` (+ `Workstation Type`) is canonical, extended with `production_line` (Link, grouping for line scheduling/T19) and `division` (Link, plant-area tree).

**Mapping:** Qcadoo `Workstation`/`ProductionLine`/division tree ≈ Workstation + production_line + division; ERPNext Workstation = as-is; OFBiz `FixedAsset` machine groups ≈ Workstation records (asset accounting stays with group ERP — mismatch "machine as accounting asset" resolved by separating operational resource (MES) from asset ledger (ERP)).
