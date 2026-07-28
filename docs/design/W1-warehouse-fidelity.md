# W1 warehouse physical fidelity + reservations (W1-5 / W1-6)

This note records how the `warehouse` module absorbs Qcadoo's physical-warehouse
behaviour onto the ERPNext substrate without forking any anchor DocType. It covers
URS-W1-018…021 (W1-5) and URS-W1-023…025 (W1-6), and the FEFO parity contract
`CHAR-FEFO-PICK-01`.

Architectural rule (ADR-005/007/008): **the anchor Stock Ledger is the single source of
quantity truth.** Everything below is either a reference/identification layer, an ordering
rule, or a reservation expressed on the anchor `Stock Reservation Entry`. No new quantity
ledger is introduced, and no anchor DocType is edited — all extensions are new DocTypes,
Custom Fields, a Property Setter and hooks owned by `rheinwerk_mes`, created idempotently
by `rheinwerk_mes/setup/w1_warehouse.py` (run from `after_install` and `patches.txt`).

## Handling Unit — reference layer, not a second quantity store (URS-W1-018)

`Handling Unit` (`HU-.######`, type Palette/Gitterbox/IBC/Fass/Big Bag) is an
identification and grouping object for pallets/load units. Its `contents` child rows
reference item + batch + a **reference** quantity + storage location. Re-implements the
Qcadoo lot-level pallet affordance (`ResourceFields.java:32-90`, `palletNumber` /
`typeOfLoadUnit` / `storageLocation`).

Why it can never become a parallel quantity store:

- the DocType has **no submit/ledger lifecycle** — saving a Handling Unit posts no Stock
  Ledger Entry (asserted in `test_tc_w1_019_handling_unit_is_not_a_second_quantity_store`);
- on `validate`, `set_reconciliation_flag()` compares each `(item, batch)` reference
  quantity against the anchor ledger balance in the unit's warehouse
  (`availability.ledger_balance`). A unit may hold *part* of a batch (content ≤ ledger),
  but if it declares *more* than the ledger records, `reconciliation_flag` is raised for a
  clerk to reconcile — the flag never overrides the ledger.

## Storage Location — warehouse-scoped tree (URS-W1-019)

`Storage Location` is a Frappe nested set (`is_tree`, `nsm_parent_field =
parent_storage_location`) below the anchor Warehouse, modelled on the existing `Division`
tree. Each node carries its `warehouse`. Scoping is enforced in two places:

- `StorageLocation.validate` rejects a child whose parent belongs to a different warehouse;
- `HandlingUnit.validate` rejects a location whose warehouse differs from the unit's, so a
  location for RM Lager Nord (e.g. `NORD-A-01-01`) cannot be attached to a unit in
  FG Lager Süd (URS-W1-019 AC-2).

Storage locations are also referenceable from Stock Entry rows and Batches
(Custom Fields), so a movement/batch can record *where* without holding quantity.

## Disposal algorithms — per warehouse (URS-W1-020)

Unlike the anchor's single global stock setting, the disposal strategy lives on each
Warehouse via the `disposal_method` Custom Field (extended in W1 to add **LEFO**:
`\nFEFO\nFIFO\nLIFO\nLEFO`). Fixtures: RM Lager Nord = FEFO, FG Lager Süd = FIFO.

Ordering is a **pure function** in `warehouse/contracts.py::picking_order`, which is the
W0 handover entrypoint (`tests/characterisation/api.py` `ENTRYPOINTS["picking_order"]`).
Re-implements — never ports — the Qcadoo enum and search orders:

| Algorithm | Qcadoo code | Search order (`SearchOrders`) |
|---|---|---|
| FIFO | `01fifo` | ascending intake `time` |
| LIFO | `02lifo` | descending intake `time` |
| FEFO | `03fefo` | ascending `expiration_date`, then ascending `available_quantity` |
| LEFO | `04lefo` | descending `expiration_date`, then ascending `available_quantity` |
| _unknown_ | — | falls back to **FIFO** (`WarehouseAlgorithm.parseString`) |

Citations: `WarehouseAlgorithm.java:26-27,38-48`,
`ResourceManagementServiceImpl.java:1015-1027,1207-1220`
(`getResourcesForWarehouseProductAndAlgorithm`), `SachetCognition/Chem_mes@master`.

`warehouse/disposal.py` is the site-facing adapter: it reads the warehouse strategy, builds
resource mappings from the ledger batch balances (in exactly the characterisation-fixture
shape) and delegates to `picking_order`; `allocate()` greedily fills demand in that order.
Because the site path and the offline `CHAR-FEFO-PICK-01` fixture share one ordering rule,
the frozen parity fixture now executes against production code with no test change.

### Intentional policy note — expired batches in disposal ordering

`disposal.resources_for_warehouse` includes expired-but-physically-present batches
(`ledger_balance(..., consider_expired=True)`) so FEFO/LEFO still *order* them. Refusing to
**issue** an expired batch is a separate hard-stop gate owned by the expiry child
(URS-W1-013 / the non-parity legs of TC-W1-030); the disposal ordering rule itself stays
faithful to Qcadoo, which orders by expiry rather than filtering. This keeps the two
concerns cleanly separable across module owners.

## Batch-aware movements on the anchor ledger (URS-W1-021)

`warehouse/movements.py` maps the Qcadoo document taxonomy
(`DocumentType.java:31-35`) onto anchor Stock Entry purposes — Receipt→Material Receipt,
Release→Material Issue, Transfer→Material Transfer — and posts a single batch-aware Stock
Entry (`use_serial_batch_fields` + `batch_no`, one Serial and Batch Bundle) per movement.
Storage location / handling unit are recorded as row references when those Custom Fields
exist. There is no parallel movement store; balances are always read back from the ledger.

## Reservations (URS-W1-023 / URS-W1-024 / URS-W1-025)

Reconciles Qcadoo "draft makes reservation" (`ReservationsService.java:81-247`) with the
anchor `Stock Reservation Entry` (SRE) so document- and order-level reservations share one
mechanism (ADR-008 / CDM-06).

- **Draft document (URS-W1-023/024).** A `draft_reservation` Custom Field flags SREs, and a
  Property Setter extends `SRE.voucher_type` with `Stock Entry`. `Stock Entry` doc-event
  hooks keep reservations in sync: `on_update` (while draft) creates/refreshes one
  draft-flagged SRE per source row via `reserve_for_draft_document`; `on_trash`/`on_submit`/
  `on_cancel` release them via `release_for_draft_document`. Draft SREs stay in **Draft**
  (docstatus 0) so they reduce *available* qty without the bin/reserved side-effects that
  submission posts — exactly a Qcadoo draft reservation. Per-warehouse opt-in via the
  `draft_makes_reservation` Custom Field (mirrors Qcadoo's document-position toggle).
- **Order level (URS-W1-025).** `reserve_for_order(work_order)` creates an SRE per required
  component against the Work Order, in the warehouse that actually holds the stock; it is
  idempotent and visible from the order. `release_for_order(work_order)` cancels submitted
  and deletes draft order SREs, returning the count.

### Availability & release API (handover to the execution-gating child, URS-W1-008/009)

```python
rheinwerk_mes.warehouse.availability.available_qty(item, warehouse) -> Decimal  # on hand − live reservations
rheinwerk_mes.warehouse.reservations.release_for_order(work_order) -> int        # cancels that order's reservations
```

`available_qty` = anchor ledger balance − sum of live (draft + submitted, not cancelled)
SRE outstanding reserved qty. On-hand is never reduced by a reservation; only *available*
shrinks — the Qcadoo quantity/availableQuantity distinction.

## Ambiguity decisions

- **HU divergence.** URS-W1-018 AC-2 requires "no independent quantity that can diverge
  without a reconciliation flag" but does not prescribe the comparison. We treat the ledger
  as truth and flag only *over-declaration* (HU content > ledger), since holding part of a
  batch on a pallet is normal and must not be flagged.
- **Order reservation warehouse.** The fixture Work Order's required-item
  `source_warehouse` (`Stores - RWC`) holds no stock. Rather than create an unusable
  zero-qty reservation, `reserve_for_order` reserves in the first candidate warehouse
  (required-item source → WIP → order source) that actually holds the component.
- **Draft SREs kept unsubmitted.** Submitting an SRE posts reserved-qty into the bin and
  validates against available stock (`before_submit`), which is order-fulfilment
  behaviour, not a soft draft reservation. Keeping draft reservations at docstatus 0
  matches Qcadoo's semantics (available drops, on-hand and bin untouched).

## Traceability

| URS | TC | Test |
|---|---|---|
| URS-W1-018 | TC-W1-019 | `test_w1_warehouse_handling_unit.py` (no-SLE + reconciliation flag) |
| URS-W1-019 | TC-W1-020 | `test_w1_warehouse_handling_unit.py` (tree scoping + HU rejection) |
| URS-W1-020 | TC-W1-021 | `test_w1_warehouse_disposal.py` (per-warehouse FEFO/FIFO + allocate) |
| URS-W1-020 | CHAR-FEFO-PICK-01 (TC-W1-030) | `test_w1_warehouse_disposal.py` (production contract + 4-algorithm) |
| URS-W1-021 | TC-W1-022 | `test_w1_warehouse_movements.py` (purpose mapping + batch-aware receipt/issue) |
| URS-W1-023 | TC-W1-024 | `test_w1_warehouse_reservations.py` (draft makes reservation) |
| URS-W1-024 | TC-W1-025 | `test_w1_warehouse_reservations.py` (delete releases reservation) |
| URS-W1-025 | TC-W1-026 | `test_w1_warehouse_reservations.py` (order-level SRE + release_for_order) |
