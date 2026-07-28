# W3-3 / W3-4 / W3-7 — group-ERP boundary

**Backlog:** W3-3 (group-ERP interface), W3-4 (boundary costing), W3-7 (external-sync freeze)
**Requirements:** URS-W3-010…014, URS-W3-019, URS-W3-021, URS-W3-022
**Test cases:** TC-W3-013…017, TC-W3-023
**Code:** `rheinwerk_mes/integration/boundary/**`, `rheinwerk_mes/setup/w3_boundary.py`,
app-owned DocTypes under `rheinwerk_mes/integration/doctype/`, health page under
`rheinwerk_mes/integration/page/interface_health/`
**Evidence:** `docs/evidence/W3-external-sync-register.md`
**Legacy baseline (semantics only, never ported):** `SachetCognition/Chem_mes@81d6bb5` —
`orders/constants/OrderFields.java:48,88` (`externalNumber` / `externalSynchronized`),
`masterOrders/constants/MasterOrderFields.java:40,42`,
`deliveries/.../ProductSynchronizationService` (the dormant WMS product sync);
`SachetCognition/Chem_erpnext@31e7970` — `controllers/stock_controller.py` (perpetual-inventory
GL the MES does *not* keep), `erpnext_integrations/**`, `edi/**` (shipped, unconfigured).

ADR-002 fixes the boundary: **orders in, confirmations out, GL postings out** — and nothing
else. Finance, buying and selling stay permanently on the group-ERP side; the MES keeps no
financial ledger of record. The group ERP does not exist in this environment, so the boundary is
exercised through committed contract fixtures and an injectable loopback transport.

## 1. Sequencing: the survey came first (W3-7)

URS-W3-019 blocks the contract freeze, so the register was produced before a single schema was
written. Its findings shaped the contract:

* No external WMS and no configured external ERP interface exists in the estate. The Qcadoo
  `externalNumber` / `externalSynchronized` pair is *dormant* — declared on eleven entities,
  read by view hooks, never written by any client. Plant C ships integrations (Plaid, Webhook,
  EDI code lists, e-mail, telephony) but configures none.
* Therefore **no legacy protocol is carried**. Legacy external references are carried as
  *data* (`external_order_ref`, `legacy_refs`), and the boundary consists of exactly the three
  new contract message types.
* Four register entries are dispositioned *carry* and each names a contract fixture (XS-01,
  XS-02 → orders in; XS-17 → GL postings out; XS-18 → confirmations out); five are *replace*
  (met by migration or a platform feature); nine are *retire* (across the ADR-002 boundary or
  superseded inside the MES).

Dossier open question §8.2 #6 is answered in the register document.

## 2. Contract v1.0

Schemas live in `rheinwerk_mes/integration/boundary/contract/v1.0/` (directory `v1.0`,
version string `1.0`) and are validated by a dependency-free JSON-Schema subset validator
(`schema.py`) — the contract suite must run in the offline CI job, so it may not need a site or
a third-party validator. Supported keywords: `type`, `required`, `properties`,
`additionalProperties`, `enum`, `const`, `pattern`, `minimum`, `exclusiveMinimum`, `minLength`,
`minItems`, `items`, `format: date` / `date-time`.

| Message type | Key fields | Once-only key |
|---|---|---|
| `orders-in` | `external_order_ref`, `demand{item_code, quantity, uom, warehouse, required_by}` | `orders-in:<message_id>` |
| `confirmation-out` | `production_order`, `external_order_ref`, `item_code`, `produced_quantity`, `uom`, `batches[]` | `confirmation-out:CONF-<order>` |
| `gl-posting-out` | `voucher{doctype,name,stock_ledger_entry}`, `warehouse`, `currency`, `lines[{account,debit,credit}]` | `gl-posting-out:GL-<sle>` |

**Versioning policy (URS-W3-013 AC-2).** `schema.requires_version_increment(old, new)` reports
an incompatible change — a new required property, a removed property, a narrowed enum, a changed
type — and `incompatibilities()` names each one. An incompatible change gets a new directory
(`v1.1`); both versions are then discoverable by `versions()` and a message is validated against
the version *it declares*, which is the transition window the AC asks for. Additive optional
properties stay inside v1.0.

**Fixtures** live only in `rheinwerk_mes/integration/boundary/fixtures/` (never inlined in
tests) with a `manifest.json` declaring case, message type, schema validity, expected reason
code and the register ids each fixture covers. Ten fixtures cover happy / duplicate / rejection
for all three message types; the manifest drives a parametrised test, so adding a fixture
automatically adds a test.

## 3. One durable store behind every queue

`Boundary Message` (app-owned) is the error queue, the hold queue, the outbox and the
idempotency ledger at once — one row per contract message, named by
`<message_type>:<message_id>`.

| Status | German | Meaning |
|---|---|---|
| `Verarbeitet` | processed | inbound message accepted |
| `Zugestellt` | delivered | outbound message accepted by the endpoint |
| `In Warteschlange` | queued | durable outbox (endpoint unreachable) |
| `Abgelehnt` | rejected | error queue, machine-readable `reason_code` |
| `Zurückgehalten` | held | unmapped-warehouse hold queue |

`queues.record()` upserts on the idempotency key: a redelivery bumps `attempts`, refreshes the
payload (so a corrected or remapped message is the one replayed) and never creates a second row.
That single property is what makes "no duplicate demand" and "no duplicate delivery" structural
rather than a caller obligation.

**Audit (URS-W3-021).** Every write goes through the existing W1 gate audit
(`execution_gating/audit.py` → `Execution Gate Log`): attention statuses are logged as refusals,
terminal ones as executed transitions, with actor, timestamp, reference and outcome. Gates:
`erp_boundary_inbound`, `erp_boundary_outbound`, `erp_boundary_replay`.

## 4. Orders in (URS-W3-010)

`inbound.process(payload)` validates against the frozen schema, then resolves the item, the
warehouse (accepting the group ERP's name with or without the company suffix) and the UOM
*before* anything is written; the write itself runs inside a savepoint. An unknown item is
therefore rejected with `UNKNOWN_ITEM` plus the JSON path of the offending field and leaves no
partial row. Accepted demand becomes `ERP Sales Input`, keyed uniquely by `external_order_ref`
and available to Production Plan creation.

Duplicate handling deliberately looks at the *outcome*, not just the key: only a message that
was accepted before is a duplicate. A previously rejected message is reprocessed on redelivery,
which is what makes "correct the master data and resend" work — and what makes replay from the
health surface identical to a resend.

## 5. Confirmations out (URS-W3-011)

Trigger: the W1 state machine. `outbound.on_work_order_update` fires on the anchor Work Order's
`on_update` / `on_update_after_submit` and emits only when `exec_state == Completed`. The message
id is derived from the order (`CONF-<order>`), so any further write to a completed order emits
nothing more — exactly one confirmation per completion.

Produced FG batches are read through the W2 genealogy movement reader
(`genealogy.links.movements_of`), so the confirmation names exactly the batches the genealogy
names, including batches booked through a `Serial and Batch Bundle`.

The message is queued **before** the transport is touched. `EndpointUnavailable` leaves it in the
outbox with reason `ENDPOINT_UNAVAILABLE`, visible as backlog on the health surface;
`flush_outbox()` delivers it on recovery, once.

## 6. GL postings out (URS-W3-012)

`Stock Entry.on_submit` → `gl.emit_for_voucher()`: one boundary posting per value-bearing stock
ledger entry (`|stock_value_difference| ≥ 0,005`), mapped through `Group ERP Account Map`
(warehouse → group-ERP stock account, offset account, currency) into a balanced debit/credit
pair. The direction of the value movement decides the side: an inbound movement debits the stock
account, an outbound one credits it.

An unmapped warehouse is the safety case: the payload is stored as `Zurückgehalten` with reason
`UNMAPPED_WAREHOUSE`, a German-first alert naming the warehouse and the missing map entry is
published (realtime + `Error Log`), and `transport().send` is never reached. The withheld payload
keeps its empty account codes on purpose — it is refused by the frozen schema, which is the
machine-checkable proof that a wrong posting cannot leave the MES. `gl.release(name)` re-attempts
one held posting once the map entry exists; replay is per message, so releasing the selected
posting never pushes its warehouse's other holds across the boundary.

The seeded map covers `FG Lager Süd` only; `RM Lager Nord` stays unmapped by design so the hold
path is demonstrable on any seeded site.

## 7. Health surface and replay (URS-W3-014)

`health.metrics()` answers counts per status and message type, error-queue depth, hold-queue
depth, outbox depth and the oldest unprocessed message (with a `DD.MM.YYYY HH:mm` display and an
age in hours) from one table. `health.kpi_tile()` is the plain-language tile B. Vogel reads —
*"ERP-Nachrichten mit Handlungsbedarf: 1"* — whose drill-down is a filter over the very same
`Boundary Message` rows, not a separate report. The Desk page `interface-health` renders the tile,
the counters and the dense queue with status pills that carry text (never colour alone).

Replay (`health.replay`, `health.replay_all`) is authorised and audited: an unauthorised attempt
is refused naming the required role *and* logged as a refusal; an authorised replay writes one
`erp_boundary_replay` entry with actor, timestamp, message reference and outcome, on top of the
status audit `queues.record` writes.

**Recorded decision (spec ambiguity).** TC-W3-017 step 2 has P. Krüger (planner) replay a
corrected message, while TC-W3-027 step 3 foresees a separate interface-admin permission.
`REPLAY_ROLES` therefore names `Rheinwerk Planner`, `Rheinwerk Interface Admin` and
`System Manager`: today the planner is authorised (TC-W3-017), and when the W3 permission-matrix
child creates the interface-admin role it only has to drop the planner from that tuple —
no boundary code changes.

## 8. Transport injection

`transport.py` defines a one-method protocol (`send(message) -> receipt | None`, raising
`EndpointUnavailable`). The transport in force comes from the `rheinwerk_boundary_transport` hook
(default: `LoopbackTransport`), cached per hook path because a transport is stateful. W4 points
the hook at a real endpoint; nothing in `outbound.py` or `gl.py` changes. Tests inject through
`transport.set_transport()`.

## 9. Installation

`setup/w3_boundary.py` (invoked from `after_install` and `patches.txt`) idempotently creates the
Work Order Custom Fields (`rw_boundary_section`, `rw_external_order_ref` — no anchor fork), the
page role permissions and the default account map. `fixtures/seed.py` seeds the account map and
plays two orders-in fixtures so a freshly seeded site already shows a populated boundary.
