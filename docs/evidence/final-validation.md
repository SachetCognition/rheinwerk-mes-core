# Final validation — consolidated MES (W0–W3) on the running local stack

Validation of the consolidated Rheinwerk MES on a locally running Frappe/ERPNext stack with
persistent MariaDB and Redis data. Every step below was executed against the live site
`dev.localhost`, not against a test double.

* Substrate: Chem_erpnext (`develop`) + `rheinwerk_mes` installed as a second app.
* Entrypoint: `scripts/setup_stack.sh` (build/seed) and `scripts/start_stack.sh` (run).
* Scope: W0 foundation, W1 production core, W2 traceability and quality, W3 planning and
  boundary. W4 cutover is deliberately out of scope.

## Result summary

| Block | Subject | Result |
|---|---|---|
| A | Stack, persistent data, restart survival | pass |
| B | W0 canonical masters, personas, three-source migration | pass |
| C | W1 recipe governance, order lifecycle, execution gates, shop floor | pass |
| D | W2 genealogy, e-signature, blocking, ISA-88, migration rollback | pass |
| E | W3 boundary, MRP/scheduling, capacity, SCADA, replay RBAC, ADR | pass |

Suite on a from-scratch site: **655 passed, 1 declared xfail**. Ruff clean; 373 files
format-clean. Evidence packs: W0 8/8, W1 10/10, W2 11/11, W3 8/8 — all complete, zero
unlinked.

## A — Stack and persistence

The stack starts from a single entrypoint, both apps install on one site, fixtures seed
idempotently, and the seeded estate survives a full stop/start of MariaDB, Redis and bench.

* `A1-home-workspace.png` — workspace after start.
* `A2-work-orders-seeded.png` — seeded orders before restart.
* `A3-after-restart-data-survives.png` — identical records after the restart.

## B — W0 foundation

Canonical masters (company RWC, items `RW-CHM-0001…0004`, warehouses, quarantine location
`NORD-Q-01`, line `LINE-1`, operations `MIX`/`FILL`), the six personas with their roles, and
the three-source master-data migration.

Migration `run_all` reconciles Plant A (Qcadoo), Plant B (OFBiz) and Plant C (ERPNext) with
source and re-export checksums matching per entity. The OFBiz item `RHEINOL-40-LB` is
quarantined as `unmappable_uom` rather than silently converted — an exception is reported,
not an invented conversion.

* `B1-items.png`, `B2-personas.png`.

## C — W1 production core

**Recipe governance.** `BOM-RW-CHM-0003-001` reaches `Accepted` with all seven structure
validators passing, an e-signature on acceptance, an in-use lock while an order runs, and a
readable `Freigabehistorie`.

**Order lifecycle.** `PO-2026-0001` runs `Pending → Accepted → In Progress` on the anchor
Work Order, with `Fertigungslinie = LINE-1` and `Stock UOM = Kg`.

**Refusals.** Each names rule, record and resolution:

* Expired batch `BATCH-A-0002` (expiry `30.06.2026`) refused for consumption — the signed
  URS-W1-030 hard stop, resolved by unexpired stock or a QA disposition.
* A draft Work Order refuses `Pending → Accepted` until it is submitted.

**Shop floor.** The scanner-first terminal resolves a scanned order number to its job with
48 px targets, German labels and kilograms.

* `C1-recipe-governance.png`, `C2-expiry-gate-refusal.png`, `C3-shopfloor-terminal-scan.png`,
  `C4-order-state-actions.png`, `C5-transition-refusal-draft.png`, `C6-order-in-progress.png`.

## D — W2 traceability and quality

**Trace Ribbon.** Multi-level genealogy `SUP-K7-0001 → BATCH-A-0001/0002 → BATCH-C-1001`,
each node carrying material, quantity, expiry in `DD.MM.YYYY`, QA state and hazmat class.

**Electronic signature.** With the `esignature_enforced` estate switch on:

1. an unsigned block is refused, citing URS-W2-029 / DEC-W2-029 with rule, record and
   resolution;
2. a wrong password is refused at re-authentication;
3. a correct signature permits the block and writes an audit row with
   `act = qa_state:Blocked`, meaning `Gesperrt`.

The switch is documented as off until cutover, so this behaviour is opt-in by design.

**Blocking propagation.** Blocking `BATCH-A-0001` leaves descendant states untouched but
raises an amber `Gesperrter Vorgänger: BATCH-A-0001` advisory on `BATCH-C-1001`, and both
become unpickable with a rule/record/resolution refusal.

**ISA-88 scaling.** `BOM-RW-CHM-0003-001` scales 500 → 600 kg, moving 480 → 576 kg and
20 → 24 kg into a new BOM version whose governance record starts in Draft. Scaling to
25 000 kg is refused against the 600 kg vessel ceiling, naming the unit procedure, the
workstation `MIX-01` and the offending phases.

**Migration rollback.** A pilot run is reversed by run id, restoring exactly the records
that run touched.

* `D1-trace-ribbon.png`, `D2-block-propagation.png`.

## E — W3 planning and boundary

**Group-ERP boundary.** The frozen contract v1.0 is idempotent: a redelivered `ERP-IN-001`
writes no second demand. `ERP-IN-002` is rejected as `UNKNOWN_ITEM` with the JSONPath
`$.demand.item_code` and no partial write.

**Schedule board.** `LINE-1` schedules two orders with realization times taken from the
TJ/TPZ norms — 200 kg = 225 min and 10 kg = 54 min — and a 45 min changeover inserted
between them, so sequence 20 starts at `10:30` after sequence 10 ends at `09:45`. The plan
moves `Entwurf → Freigegeben` and becomes operative, stamped with the deciding planner.

**Capacity refusal.** A competing plan over the same window is refused because
`LINE-1/MIX-01` is at 1 of 1 bookings; the message names the blocking booking and the
earliest feasible slot `10.03.2026 08:30`. Approval is refused on the same grounds, so the
gate cannot be bypassed by approving directly.

**Interface health and replay.** The dashboard reports totals, the error queue and the
oldest unprocessed message. Replay is refused for the operator persona and permitted for the
interface administrator, per URS-W3-023 — and a replayed invalid message stays rejected
rather than being forced through.

**Hazmat dispatch.** Scanning `BATCH-C-1002` renders the ADR 5.4.1.1.1 transport description
`UN 1263, FARBE, 3, III, (D/E)` with tunnel restriction code, GHS02 pictogram, TRGS 510
storage class, AwSV water-hazard class and the SDS reference. Removing a mandatory element
flips the verdict to the blocker `adr_packing_group`, which suppresses dispatch.

* `E1-schedule-board.png`, `E2-interface-health.png`, `E3-adr-dispatch-label.png`.

## Defects found and fixed during this validation

Rebuilding the site from scratch exposed two genuine fresh-site defects in the fixture
seeder, both fixed here:

1. **Setup wizard aborted on a fresh site.** When `frappe` is already flagged
   setup-complete, the wizard refills every later stage's locale from System Settings; those
   were empty, so the ERPNext stage received `country=None` and raised
   `AttributeError: 'NoneType' object has no attribute 'replace'`.
2. **Readings rendered in the English number format.** For the same reason the German
   `number_format` was never applied, so a density reading stored as `1.04` instead of
   `1,04`, breaking the i18n rule in URS-W2-013.

`_complete_setup_wizard()` now writes the German locale to System Settings before invoking
the wizard.

## Known limitations

* The e-signature gate is enforced only when `esignature_enforced` is set; it ships off, as
  DEC-W2-029 schedules estate-wide enforcement to cutover.
* The Plant A expiry parity contract remains a declared strict xfail — the signed divergence
  from Qcadoo's advisory FEFO behaviour recorded in DEC-W1-030.
* The substrate is pinned to `develop` (ERPNext/Frappe 17-dev) because no `version-16`
  branch exists in the fork.
