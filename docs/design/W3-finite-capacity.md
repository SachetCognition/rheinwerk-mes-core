# W3-2 — Finite-capacity layer: line schedules, TJ/TPZ times, changeover norms

Design note for **URS-W3-005 … URS-W3-009** (`docs/urs/URS-W3-planning-boundary.md` §3.2),
verified by **TC-W3-006 … TC-W3-012** (`docs/test/TST-W3-planning-boundary.md`).

The layer is *over* the anchor, never inside it: production orders stay anchor `Work Order`
documents carrying the W1 `exec_state`, work centres stay anchor `Workstation` records with
their `production_capacity`, and the capacity refusal is raised with the anchor's own
`CapacityError`. Everything W3-2 adds is app-owned: four new DocTypes, the pure calculators
in `rheinwerk_mes/manufacturing_core/scheduling/`, one workflow and one Desk page.

## Components

| Artefact | Kind | Purpose |
|---|---|---|
| `Line Schedule` | new DocType | a line's plan; carries `schedule_state`, `is_operative`, the decision and its reason |
| `Line Schedule Entry` | child table | one order's place in the sequence: start, end, realization minutes, changeover minutes and its note |
| `Line Schedule Operation` | child table | the TJ/TPZ breakdown per routed operation, and the booking the slot search reads |
| `Operation Time Norm` | new DocType | TPZ (setup) and TJ (min/kg) per operation, work centre and line |
| `Line Changeover Norm` | new DocType | changeover minutes between two products on a line |
| `scheduling/schedule_state.py` | module | the Draft → Approved / Rejected machine |
| `scheduling/realization_time.py` | module | TJ/TPZ arithmetic (pure, offline-testable) |
| `scheduling/changeover.py` | module | changeover-norm matching with Qcadoo's precedence |
| `scheduling/sequencing.py` | module | pure sequencing of a line's orders including changeovers |
| `scheduling/capacity.py` | module | the retained slot search, its modal refusal and its audit row |
| `scheduling/lifecycle.py` | module | the only writer of `schedule_state` |
| `scheduling/board.py` + `page/schedule_board` | read API + Desk page | the planner's virtualized board |
| `setup/w3_scheduling.py` | installer | workflow, capacity backfill, page roles — idempotent, from code |

## Schedule lifecycle (URS-W3-005)

`schedule_state` is a three-state machine with two edges:

```
Draft ──Plan freigeben──▶ Approved   (operative sequence of the line)
  └────Plan ablehnen───▶ Rejected    (no operative effect)
```

* Only orders in `exec_state` **Accepted** enter a schedule (AC-1) — `lifecycle.schedulable_orders`.
* Approving marks the schedule `is_operative`; the previously operative schedule of the same
  line steps back, so a line always has exactly one operative sequence (AC-2).
* Rejecting writes no plan effect at all: `is_operative` stays 0 (AC-2).
* Every transition and every refusal is written to the W1 `Execution Gate Log`
  (`execution_gating.audit`), so the audit trail of a plan decision matches the one of an
  order decision (URS-W3-021).
* `Line Schedule.validate` refuses any `schedule_state` write that did not come through
  `lifecycle`, so the machine cannot be bypassed by a direct `save`.

### Decision D-W3-2-A — the legacy `Approved → Rejected` edge is dropped

`ScheduleState.java:8-24` (Qcadoo) allows three edges:

```java
DRAFT      → APPROVED | REJECTED
APPROVED   → REJECTED
REJECTED   → (terminal)
```

URS-W3-005 AC-3 and TC-W3-007 fix the *target* set to exactly
`{Draft → Approved, Draft → Rejected}` and require both `Approved → Draft` and
`Rejected → Approved` to be refused. The specification is therefore deliberately narrower
than the donor for one edge, and the reading chosen here is the specification's:

* an **Approved** schedule is the operative sequence a shop floor is already working to;
  retro-rejecting it would leave the line without a plan and without a replacement,
* the supported way to change an approved plan is to create a **new Draft** and approve it,
  which supersedes the old one and leaves both documents in the audit trail,
* Qcadoo's extra edge exists because its schedule has no successor concept; the target has
  one (`is_operative`), so the edge is redundant rather than lost.

The narrowing is **measured, not described**: the `CHAR-SCHEDULE-STATE-01` fixture case
`SCHED-08-approved-to-rejected-narrowed` is flagged `new_behaviour` and carries both
expectations — the legacy verdict (allowed) against the fixture-encoded rule and the target
verdict (refused) against the implementation. If either side ever changes, the contract
fails.

## Realization times from TJ/TPZ (URS-W3-006)

`realization_time.operation_duration` re-expresses
`OrderRealizationTimeServiceImpl.java:156-186`:

```
cycles      = quantity / workstations           (maxForWorkstation)
cycles      = ceil(cycles)                      (TJ not divisible)
run_min     = trunc(cycles × TJ × staff_factor) (BigDecimal.intValue — truncation, not rounding)
duration    = run_min + TPZ                     (once per work centre, or per workstation)
```

Norms live in `Operation Time Norm`; the seeder ships MIX (TPZ 30, TJ 0,6 min/kg) and FILL
(TPZ 15, TJ 0,3 min/kg) on the LINE-1 work centres, which gives URS-W3-006 AC-1 exactly:

| Operation | Setup | Run | Duration |
|---|---|---|---|
| MIX (500 kg) | 30 min | 500 × 0,6 = 300 min | **330 min** |
| FILL (500 kg) | 15 min | 500 × 0,3 = 150 min | **165 min** |
| PO-2026-0001 total (sequential routing) | | | **495 min** |

Parity is pinned by `CHAR-REALIZATION-TIME-01` over 15 combinations including the edge values
`quantity = 1` (run time truncates to 0, only TPZ remains) and `TPZ = 0`, plus the multi-
workstation, non-divisible-TJ, staff-factor and surcharge branches (TC-W3-009).

Qcadoo's parallel-branch offset arithmetic (`:95-125`) is **not** re-implemented: every
Rheinwerk routing is a chain, so the order total is the plain sum. A future branched routing
would extend `sequencing.py`, not the per-operation calculator.

## Changeover norms (URS-W3-007)

`changeover.best_matching` re-expresses `ChangeoverNormsSearchServiceImpl.java:48-64`:
candidates are the norms of the sequenced line plus the line-agnostic ones; the winner is the
most specific changeover type (a norm naming both products beats one naming any successor),
then the line-specific norm, then the newest. A norm naming the same product twice is the
inter-batch flush — the seeded LINE-1 norm is 45 min between two Rheinol 40 batches.

Sequencing inserts the matched minutes between two consecutive orders, so the second order
starts at `previous end + changeover`. When nothing matches, **no time is inserted** and the
transition is annotated with the machine-readable `no changeover norm`, which the board
renders as *keine Umrüstnorm* (AC-2) — the absence is visible instead of silent.

## Capacity refusal (URS-W3-008)

The substrate's behaviour is adopted, not reimplemented: the ceiling is the anchor
`Workstation.production_capacity` and the exception raised is ERPNext's own `CapacityError`
(`work_order/services/operations.py:105-130`), so anchor handlers keep working. What the app
adds is presentation and audit. On approval, every operation of the schedule is slot-searched
against the operations of *other operative* schedules at the same work centre; when the
overlapping bookings reach the capacity, the approval is refused with a hard-gate modal:

* **Regel** — the capacity rule, naming the work centre as `LINE-1/MIX-01`,
* **Datensatz** — the refused order and operation plus the blocking booking (order, schedule,
  its end),
* **Behebung** — the earliest feasible slot, i.e. the earliest end among the blocking
  bookings, formatted DD.MM.YYYY HH:MM.

The same text (HTML stripped) is written to the `Execution Gate Log` under the gate
`capacity_slot_search`, so the refusal is a record and not only a message.

## Schedule board performance (URS-W3-020)

The board is designed for the 200-order budget from the start:

* the server returns **pages** of pre-formatted rows (`board.board_rows`, 100 per call) — one
  `get_all` per page, no per-row document loads, no locale work on the client;
* the table is **virtualized**: a fixed 32 px row height lets the client paint only the
  visible window plus a small overscan, with spacer divs carrying the scroll height, so DOM
  size is independent of the schedule length;
* rows not yet fetched paint as placeholders and trigger exactly one fetch for their page;
* every control whose work can exceed 100 ms (reload, page fetch, approve, reject) shows
  progress on itself (`aria-busy`, disabled + spinner affordance) rather than in a toast;
* keyboard operation throughout (arrows, Enter, `F` freigeben, `A` ablehnen, Esc, `?`), state
  pills carry icon + label + tone, order identifiers are mono, dates DD.MM.YYYY, masses kg.

Shortcuts are suppressed while a field has focus or a dialog is open, so a justification
containing "f" cannot re-open the approval dialog.

Measured on the dev site with a 200-order LINE-1 schedule: head + both row pages take
26 ms end-to-end in the browser (5–8 ms server-side) and the table paints 26 rows, so the
DOM stays flat as the schedule grows. `tests/acceptance/test_w3_scheduling_board.py`
asserts the budget so a regression fails the suite instead of the review.

## Out of scope, on purpose

No constraint-based optimiser: URS-W3-009, recorded in
`docs/decisions/DEC-W3-009-optimiser-build-vs-buy.md` with a status and audited by
TC-W3-012. The sequence on a line is the planner's.

## Traceability

| URS | Behaviour | Tests |
|---|---|---|
| URS-W3-005 | line schedules of Accepted orders, Draft → Approved / Rejected | TC-W3-006 (`test_w3_scheduling_lifecycle.py`), TC-W3-007 (`test_w3_scheduling_parity.py`, `CHAR-SCHEDULE-STATE-01`) |
| URS-W3-006 | TJ/TPZ realization times, minute-exact | TC-W3-008 (`test_w3_scheduling_times.py`), TC-W3-009 (`CHAR-REALIZATION-TIME-01`) |
| URS-W3-007 | changeover norms in sequencing | TC-W3-010 (`test_w3_scheduling_changeover.py`) |
| URS-W3-008 | capacity refusal naming work centre, booking and slot | TC-W3-011 (`test_w3_scheduling_capacity.py`) |
| URS-W3-009 | no optimiser, D4 recorded with a status | TC-W3-012 (`test_w3_scheduling_scope.py`) |
