# W2-8 — Warehouse fidelity completion

Wave W2, module track **warehouse**. Extends the W1 warehouse fidelity work
(`docs/design/W1-warehouse-fidelity.md`) with the three remaining Qcadoo warehouse
journeys, keeping the anchor **Stock Ledger the single source of quantity truth** — a
Handling Unit never becomes a parallel quantity store.

| URS | Item | TC |
|---|---|---|
| URS-W2-025 | Pallet balances (Handling-Unit balances reconciled against the ledger) | TC-W2-033 |
| URS-W2-026 | Stocktaking journey (persona W. Braun) | TC-W2-034 |
| URS-W2-027 | Repacking journey | TC-W2-035 |

## Architectural stance (unchanged from W1)

The anchor Stock Ledger is the only quantity system of record. The Handling Unit
(`docs/design/W1-warehouse-fidelity.md`, ADR-005 / CDM-03) is a *reference/identification*
layer over it. Everything W2-8 adds is either:

* a **read model** over the ledger and the Handling-Unit reference (pallet balance,
  reconciliation), or
* a **journey** whose acceptance posts **anchor Stock Entries** through the W1
  `warehouse.movements.book_movement` funnel — never a bespoke quantity write.

No anchor DocType is forked. The two new documents (`Stocktaking`, `Repacking`) are
`rheinwerk_mes`-owned DocTypes; the only anchor touch is *reusing* the Batch's own native
`parent_batch` field (see the repacking section).

## State machines (follow the `exec_state` pattern)

Both journeys reuse the shape of the production-order machine
(`docs/design/W1-exec-state.md`) rather than inventing a third style
(`rheinwerk_mes/warehouse/journey.py`): an explicit `LEGAL_TRANSITIONS` table, one funnel
(`validate_transition`) every save passes through, role gating read from the DocType's
Frappe Workflow, a mandatory reason for reason-required targets, terminal-state
immutability, and an appended `state_history`.

### Stocktaking

Qcadoo baseline (semantics only, never ported):
`materialFlowResources/states/constants/StocktakingState.java:9-46`
(`SachetCognition/Chem_mes@master`).

| From \ To | Draft | In Progress | Accepted | Rejected |
|---|---|---|---|---|
| **Draft** | — | ✓ | — | ✓ |
| **In Progress** | — | — | ✓ | ✓ |
| **Accepted** (terminal) | — | — | — | — |
| **Rejected** (terminal) | — | — | — | — |

Qcadoo splits the successful tail into `IN_PROGRESS → FINALIZED → FINISHED` (both
`FINALIZED` and `FINISHED` can still be `REJECTED`; `FINISHED` is terminal). URS-W2-026
names the business journey `draft → in progress → accepted`, so **FINALIZED and FINISHED
are collapsed onto a single terminal `Accepted`** (decision D-1 below). The correcting
posting happens on entry to `Accepted`, which is the point Qcadoo posts its stocktaking
differences at `FINISHED`.

Posting semantics (`warehouse/stocktaking.py`): on acceptance, every counted line whose
count differs from the **live** ledger balance posts one correcting anchor Stock Entry so
the ledger ends exactly at the counted quantity — a count below book posts a Material Issue
(Qcadoo `RELEASE`), a count above book a Material Receipt (`RECEIPT`). Measuring against the
live ledger (not the stored book snapshot) guarantees the ledger lands on the counted value
regardless of intervening movements: **no quantity is invented or lost**. The accepted
record is then immutable.

Only one *open* (Draft / In Progress) stocktaking is allowed per warehouse (URS-W2-026
AC-2). The count sheet is filled in the warehouse's disposal-algorithm order
(`warehouse.disposal.picking_order_for_warehouse`), the order Qcadoo walks resources for a
count (`ResourceManagementServiceImpl.java:1015-1027`).

### Repacking

Qcadoo baseline (semantics only, never ported):
`materialFlowResources/states/constants/RepackingState.java:8-30`
(`SachetCognition/Chem_mes@master`).

| From \ To | Draft | Accepted | Rejected |
|---|---|---|---|
| **Draft** | — | ✓ | ✓ |
| **Accepted** (terminal) | — | — | — |
| **Rejected** (terminal) | — | — | — |

Posting semantics (`warehouse/repacking.py`), two shapes:

* **Same batch identity** (URS-W2-027 AC-1): moving `qty` between two Handling Units of the
  same warehouse and batch changes only the units' reference content rows (source −qty,
  target +qty). Because the batch and warehouse are unchanged, the **ledger balance is
  untouched** — the reference split neither invents nor loses quantity, and
  `HandlingUnit.validate` re-runs its reconciliation flag so the reference can never exceed
  the ledger.
* **New lot identity** (URS-W2-027 AC-2): a deliberate re-drumming/re-labelling mints a new
  canonical Batch carrying `parent_batch = <source>`; `qty` is issued from the source batch
  and received onto the new batch in the same warehouse, so the **item's on-hand total is
  unchanged** while `qty` kg changes batch identity. The Handling-Unit contents are updated
  to reference the new lot on the target.

`parent_batch` is the anchor Batch's **own native field** (`erpnext .../batch/batch.json`,
`parent_batch`, a read-only Link to Batch used by ERPNext batch splitting). W2-8 reuses it
for split/repack lineage — no Custom Field, no fork (TC-W2-008 still asserts the schema
diff). This split lineage is **distinct from production genealogy**: a repack writes **no**
Genealogy Link (`genealogy/**` is untouched), so `warehouse.repacking.split_lineage` reads
only `parent_batch` and never conflates with `genealogy.links`.

## Ambiguity resolutions (dossier-consistent, per programme rule 7)

* **D-1 — FINALIZED/FINISHED → Accepted.** URS-W2-026 names three states
  (`draft → in progress → accepted`); Qcadoo has five. The two extra Qcadoo states are an
  internal finalise/close split with no distinct business meaning in the URS, so they are
  collapsed onto the terminal `Accepted` where the difference posting occurs.
* **D-2 — reason required only for `Rejected`.** A rejection records why stock was not
  adjusted; acceptance needs none. Enforced by `Journey.reason_required`.
* **D-3 — correction measured against the live ledger**, not the stored book snapshot, so
  the ledger lands exactly on the counted quantity (single-truth guarantee).
* **D-4 — reconciliation key universe is the batches the pallets name.** Ledger stock never
  placed on a pallet is simply out of the pallet report's scope; over- and under-declaration
  against a named batch are both reported with a signed difference, ledger as truth.

## Files

* `warehouse/journey.py` — shared state-machine engine.
* `warehouse/pallet_balance.py` — pallet balance + reconciliation read models (URS-W2-025).
* `warehouse/stocktaking.py` + `warehouse/doctype/stocktaking{,_line}` (URS-W2-026).
* `warehouse/repacking.py` + `warehouse/doctype/repacking` (URS-W2-027).
* `warehouse/doctype/warehouse_journey_history` — shared audit child table.
* `setup/w2_warehouse.py` (+ `patches.txt`) — idempotent installer for the two journey
  Workflows and their role gating.
* `fixtures/seed.py` — `seed_pallets()` seeds pallet `HU-000123` (500 kg BATCH-A-0001 at
  NORD-A-01-01) and an empty repack target `HU-000124`.
* Tests: `tests/acceptance/test_w2_warehouse_{pallet_balance,stocktaking,repacking}.py`.

Published W1 signatures (`availability.available_qty`, `reservations.release_for_order`,
`contracts.picking_order`) are unchanged.
