# W1-2 / W1-3 — execution gating and anchor hard stops

**Backlog:** W1-2, W1-3 · **Requirements:** URS-W1-005…URS-W1-013, URS-W1-033
**Test cases:** TC-W1-006…TC-W1-014, TC-W1-036, TC-W1-030 (order legs)
**Code:** `rheinwerk_mes/execution_gating/**`, `rheinwerk_mes/setup/w1_gating.py`
**Legacy baseline (semantics only, never ported):** `SachetCognition/Chem_mes@master` —
`orders/states/OrderStateValidationService.java:44-47` and `:54-63`,
`orders/states/OrderStateService.java:47-59`,
`productFlowThruDivision/listeners/OrderStatesListenerServicePFTD.java:580` (material
availability) and `:129-131`/`:633` (reservation clearing).
**Anchor baseline (adopted, verified — never re-implemented):** ERPNext
`stock_entry.py:965-975` + `work_order/services/status.py:208-224` (over-production),
`job_card.py:1452-1467` and `:904-910` (stopped freeze), `work_order.py:1131-1132`
(closed terminal), `pick_list.py:286-311` (expired batches on pick).

## 1. Where the gates live

W1-1 owns the state machine; W1-2 only *registers* gates through its documented hook, so
`manufacturing_core/exec_state.py` is untouched:

```python
# rheinwerk_mes/hooks.py (append-only)
rheinwerk_exec_state_gates = [
	… W1-1 core gates …
	"rheinwerk_mes.execution_gating.gates.acceptance_gate",
	"rheinwerk_mes.execution_gating.gates.recipe_accepted_gate",
	"rheinwerk_mes.execution_gating.gates.completion_gate",
	"rheinwerk_mes.execution_gating.gates.material_availability_gate",
]
```

Each gate receives a `TransitionContext`, judges, and refuses by appending one hard-gate
message — it never posts. Side effects that must follow a *written* transition live in
`execution_gating/side_effects.py` on the anchor `Work Order` document events, exactly as
`docs/design/W1-exec-state.md` §4 requires.

| Module | Responsibility |
|---|---|
| `contracts.py` | pure Qcadoo-parity rules over plain mappings; the W0 harness entrypoints |
| `gates.py` | anchor `Work Order` → contract mapping, availability arithmetic, refusal modals |
| `side_effects.py` | reservation release (URS-W1-009) + transition logging (URS-W1-033) |
| `expiry.py` | expired-batch consumption hard stop (URS-W1-013) |
| `anchor_stops.py` | declaration of the adopted substrate hard stops (W1-3, feeds W1-10) |
| `audit.py` + `Execution Gate Log` | immutable audit of every gated action (URS-W1-033) |

## 2. The gates

| Gate | URS | Transition | Refuses when |
|---|---|---|---|
| `acceptance_gate` | URS-W1-005 | * → Accepted | planned start, planned end, `production_line` or recipe (`bom_no`) missing; end not after start |
| `recipe_accepted_gate` | URS-W1-006 | * → Accepted | `recipe_isa88.governance.gov_state(bom_no) != "Accepted"` |
| `completion_gate` | URS-W1-007 | * → Completed | execution dates missing; recorded output (`produced_qty`) = 0 |
| `material_availability_gate` | URS-W1-008 | * → In Progress | any component's outstanding requirement exceeds `warehouse.availability.available_qty` |

The W1-1 `shortfall_gate` (produced < ordered needs a reason, URS-W1-004) keeps its place;
W1-2 adds the *zero output* rule beside it rather than merging the two.

### Canonical field mapping (CDM-02)

| Qcadoo order field | Anchor `Work Order` field |
|---|---|
| `dateFrom` | `planned_start_date` |
| `dateTo` | `planned_end_date` |
| `productionLine` | `production_line` (Custom Field) |
| `technology` | `bom_no` |
| `doneQuantity` | `produced_qty` |

### Refusal presentation ("hard gates look hard")

Every refusal is a raised modal — the state machine collects the messages and throws them
under the title *Übergang abgelehnt: <von> → <nach>*, never a toast — and each message names
the three things the design skill demands, all through `frappe._()`:

```
Regel:     Annahme erfordert Starttermin, Endtermin, Fertigungslinie und Rezeptreferenz.
Datensatz: Auftrag PO-2026-0002 — fehlende Angaben: Fertigungslinie
Behebung:  Fehlende Felder im Fertigungsauftrag ergänzen und Annahme erneut auslösen.
```

Dates render DD.MM.YYYY and masses as kg with a decimal comma (`Fehlmenge 10 kg`).

### Availability arithmetic (URS-W1-008)

Required quantity is the *outstanding* requirement (`required_qty − transferred_qty`) and
availability is `available_qty()` — on-hand minus live reservations — in the component's
source warehouse, falling back to the order's WIP/source warehouse when the component's own
source holds no stock (the same precedence the reservation side applies). Reservations the
order holds *for itself* are added back so an order never blocks on its own reservation;
every other voucher's reservation stays excluded, which is URS-W1-008 AC-3.

The gate is read-only: a refused start writes no Stock Ledger Entry and no reservation.

### Reservation release (URS-W1-009)

`side_effects.on_work_order_update` fires on `Work Order.on_update` /
`on_update_after_submit`, keys on the `state_history` row the machine just appended and, for
Declined and Abandoned, calls `warehouse.reservations.release_for_order`. Keying on the
history row makes both the release and the transition log idempotent — re-saving the order
never repeats either.

## 3. Audit of gated actions (URS-W1-033)

`Execution Gate Log` (module *Execution Gating*) is append-only: `in_create`, read-only
fields, read-only permissions, and a controller that refuses every update and delete. One
row per gate decision with `gate`, `rule`, `reference_doctype`/`reference_name`,
`from_state`/`to_state`, `detail`, `logged_by`, `logged_at` and `outcome`
(*Abgelehnt* / *Durchgeführt*) — refusals **and** executed transitions, so an order's audit
view tells the whole story next to the W1-1 `state_history`.

A refusal aborts its request, which would roll the audit row back; the row is therefore also
registered as an after-rollback callback and re-committed once the rollback completed (the
pattern Frappe uses to keep `Error Log` rows). Inside the test suite (`frappe.flags.in_test`)
that callback is not registered, so per-test rollback stays clean.

## 4. Anchor hard stops (W1-3) — adopted and verified

`anchor_stops.ANCHOR_HARD_STOPS` declares the four adopted refusals with their anchor source,
mapped TC and Parity/Divergence verdict; `tests/acceptance/test_w1_gating_anchor_stops.py`
drives ERPNext through our app and asserts each still fires. No anchor DocType is forked, no
anchor validation is bypassed, and no `ignore_validate` flag is set on a posting path.

| Stop | URS | TC | Verified behaviour |
|---|---|---|---|
| Over-production | URS-W1-010 | TC-W1-011 | 510 kg against a 500 kg order at 0 % allowance is refused and writes no SLE; 100 kg posts |
| Stopped freeze | URS-W1-011 | TC-W1-012 | a MIX job card against a Stopped order is refused, none reaches docstatus 1 |
| Closed terminal | URS-W1-012 | TC-W1-013 | `stop_unstop` refuses both *Stopped* and *Resumed* on a Closed order |
| Expired batch | URS-W1-013 | TC-W1-014 | pick list refuses on save (anchor); consumption refused by our gate (see §5) |

The 0 % over-production allowance is the estate default, pinned idempotently by
`setup/w1_gating.py` when the business has not configured one — the substrate default the
hard stop is verified against (URS-W1-010 AC-1).

## 5. Recorded divergences and one substrate gap

### D-1 — expiry policy is a hard stop (URS-W1-030, divergence, sign-off required)

Plant A/Qcadoo treats expiry as *advisory*: FEFO orders resources by expiry
(`ResourceManagementServiceImpl.java:1015-1027`) but nothing stops an expired resource from
being issued. The Rheinwerk estate deliberately adopts the stricter anchor policy: consuming
or picking an expired batch is refused. This is an **intentional divergence** carrying the
URS-W1-030 business sign-off, and is declared as such in `anchor_stops.py`
(`verdict="Divergence"`), so the W1-10 record (URS-W1-031) reports it from code rather than
by hand. The disposal *ordering* rule stays faithful to Qcadoo — expired-but-present batches
are still ordered by `warehouse.disposal` (see `docs/design/W1-warehouse-fidelity.md`); only
the outward posting is refused.

### D-2 — substrate gap: the anchor exempts stock consumption from its expiry throw

URS-W1-013 reads the anchor as refusing outward postings against expired batches
(`stock_ledger_entry.py:287-299`). On the adopted substrate that throw is **skipped for
Stock Entry vouchers** (`validate_batch`: `if self.batch_no and self.voucher_type != "Stock
Entry"`), and `stock/services/serial_batch_bundle_service.py:110-112` skips its
`BatchExpiredError` for the purposes *Material Issue* and *Material Transfer*. Verified on the
dev site: a 5 kg Material Issue from the expired BATCH-A-0002 posted silently.

Resolution, chosen as the reading most consistent with URS-W1-013 AC-1 and the URS-W1-030
policy: close the gap in `rheinwerk_mes` with `execution_gating/expiry.py` hooked on
`Stock Entry.validate` — a hook, never a fork, and strictly *additive* (it only refuses more,
never less). Intake rows are not judged: the anchor already refuses receiving an expired
batch (`serial_batch_bundle_service.py:132-147`), and the estate policy is about consumption.
The pick-list half stays purely anchor-adopted.

### D-3 — date consistency is folded into the acceptance contract

`OrderStateValidationService.validationOnAccepted` only checks the required references; the
"end after start" rule is Qcadoo's separate `OrderStateService.checkOrderDates:47-59`.
URS-W1-005 states both as one acceptance gate, so `evaluate_order_acceptance` appends
`orders.validate.global.error.datesOrder.overdue` after the `fieldRequired` errors. The frozen
`CHAR-ORDER-ACCEPT-01` fixtures are unaffected (no case has an inverted date range) and pass
verbatim — hence *Parity*, with the additional baseline cited.

## 6. Characterisation handover (TC-W1-030 order legs)

`rheinwerk_mes/execution_gating/contracts.py` implements the two entrypoints the W0 harness
resolves (`tests/characterisation/api.py`, `ENTRYPOINTS["order_acceptance"]` /
`["order_completion"]`):

```python
evaluate_order_acceptance(order: Mapping[str, Any]) -> Verdict
evaluate_order_completion(order: Mapping[str, Any]) -> Verdict
```

Both are pure functions over plain mappings (no site needed) and return the *legacy Qcadoo
message keys*, so `CHAR-ORDER-ACCEPT-01` and `CHAR-ORDER-COMPLETE-01` now execute against
production code with the frozen fixtures unchanged. `gates.py` feeds the very same rules from
the anchor document and translates the verdict into the German-first operator modal — one rule
set, two consumers, no drift. `tests/acceptance/test_w1_gating_parity.py` asserts the flip
(the contracts no longer resolve to `legacy_rules`) and re-runs every frozen case.

## 7. Setup and installation

`setup/w1_gating.py` is invoked from `after_install` (fresh site) and `patches.txt` (existing
sites); it asserts the audit log is append-only and pins the over-production allowance. Both
are idempotent, so a clean install and a migration converge — nothing in this design exists
only on a developer's site.

## 8. Traceability

| URS | Test case | Test |
|---|---|---|
| URS-W1-005 | TC-W1-006, TC-W1-030 | `test_w1_gating_order_gates.py`, `test_w1_gating_parity.py` |
| URS-W1-006 | TC-W1-007 | `test_w1_gating_order_gates.py` |
| URS-W1-007 | TC-W1-008, TC-W1-030 | `test_w1_gating_order_gates.py`, `test_w1_gating_parity.py` |
| URS-W1-008 | TC-W1-009 | `test_w1_gating_order_gates.py` |
| URS-W1-009 | TC-W1-010 | `test_w1_gating_order_gates.py` |
| URS-W1-010 | TC-W1-011 | `test_w1_gating_anchor_stops.py` |
| URS-W1-011 | TC-W1-012 | `test_w1_gating_anchor_stops.py` |
| URS-W1-012 | TC-W1-013 | `test_w1_gating_anchor_stops.py` |
| URS-W1-013 | TC-W1-014 | `test_w1_gating_anchor_stops.py` |
| URS-W1-033 | TC-W1-036 | `test_w1_gating_audit.py` |
