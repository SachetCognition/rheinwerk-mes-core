# W3-5 — SCADA / OPC-UA-Trackingereignisse

Design note for the SCADA adapter (`rheinwerk_mes/integration/scada/**`). Implements
URS-W3-015 … URS-W3-017 of `docs/urs/URS-W3-planning-boundary.md` §3.4 plus the audit
obligation URS-W3-021; test coverage TC-W3-018, TC-W3-019, TC-W3-020.

This capability is **white space** in all three legacy systems (dossier §6.3): Qcadoo, the
legacy ERPNext instance and OFBiz all rely on operators typing machine output at a terminal.
There is therefore no behaviour to absorb and no parity contract — the design below is
derived from the URS, `docs/design/W1-exec-state.md` (only an In-Progress order accepts
tracking) and `docs/design/W2-genealogy.md` (produced quantities reach the trace through the
existing APIs).

## 1. Layering — why a transport seam

```
equipment ─▶ TagEventTransport ─▶ ScadaAdapter ─▶ ingest.ingest() ─▶ OPC UA Tracking Event
              (simulated | real)   (spool, replay)   (map → match → attach → audit)   │
                                                                                      ├─▶ W1 job_execution (time log, output)
                                                                                      ├─▶ W2 links.rebuild_links_for_work_order
                                                                                      ├─▶ W1 audit.log_transition
                                                                                      └─▶ unmatched queue (planner disposition)
```

| Module | Responsibility |
|---|---|
| `contracts.py` | `TagEvent` (frozen), event types, event states, source system, 5 s budget |
| `transport.py` | `TagEventTransport` protocol, `SimulatedTransport`, `OpcUaClientTransport` (seam) |
| `buffer.py` | `SpoolBuffer` — persistent FIFO spool for store-and-forward |
| `mapping.py` | tag → work centre + event type, work-centre validation |
| `ingest.py` | matching, attachment, W1/W2 side effects, audit, unmatched queueing |
| `unmatched.py` | planner queue and its dispositions (assign / discard) |
| `adapter.py` | `ScadaAdapter` — connect/publish/replay/pump around transport + spool |
| `api.py` | whitelisted Desk entry points (`play_fixture`, `order_events`) |

### D1 — No OPC-UA client dependency, one documented seam

No OPC-UA server exists in the programme environment, so adding `asyncua` would ship an
untestable dependency. Instead the adapter takes an injectable transport.
`OpcUaClientTransport` stays in the tree so the seam is type-checked and greppable; it is the
**only** place a client library is ever imported and the import is lazy inside `connect()`.
Wiring a real plant is: add `asyncua` to the deployment requirements, implement
`_subscribe()` (one subscription per `OPC UA Tag Mapping.tag_address`, i.e. per OPC-UA
`NodeId` such as `ns=2;s=Line1.Mix01.ProducedKg`, pushing each `datachange_notification` with
the server's `SourceTimestamp` as `equipment_timestamp` into `self._inbox`). Nothing above the
transport changes — the fixture path and a live plant exercise identical matching, queueing
and store-and-forward code.

The committed simulator script is
`rheinwerk_mes/integration/scada/fixtures/line1_mix01_events.json`: a MIX start, three
25 kg counts, a MIX stop and one FILL count for a work centre without a running order.
`SimulatedTransport.from_fixture()` replays it; `api.play_fixture()` exposes it to the Desk
("Simulator abspielen") so the demo stack produces real tracking events.

## 2. Mapping (URS-W3-016)

`OPC UA Tag Mapping` is an app-owned DocType (no anchor fork), maintained by
**Rheinwerk Technologist**, read-only for planner and Manufacturing User:

| Field | Purpose |
|---|---|
| `tag_address` | the OPC-UA NodeId, unique, the document's title field |
| `event_type` | `operation-start` \| `operation-stop` \| `produced-count` |
| `work_centre_code` | CDM-08 composite code `LINE-1/MIX-01` |
| `production_line` / `work_centre` | links resolved from the code on validate |
| `operation` | optional pin to one routing operation |
| `uom` / `description` / `enabled` | kg by default, German help text, soft disable |

`mapping.resolve_work_centre(code)` splits the composite code and refuses — naming the
invalid code in the message (AC-2) — when the line or the workstation does not exist, or when
the workstation belongs to another line. `Workstation` itself is untouched: validation reads
it, the mapping stores the resolved links.

### D2 — Work centres are addressed by their CDM-08 composite code

The technologist maintains `LINE-1/MIX-01`, not an internal `Workstation` name, because that
is the identifier the plant and CDM-08 use. The resolved `production_line`/`work_centre`
links are derived, so a mapping never carries an unresolvable reference.

## 3. Ingestion and matching (URS-W3-015)

`ingest.ingest(event, late=False)` runs, for one event:

1. **resolve** the tag through the enabled mappings; an unknown address is queued;
2. **match** open (`docstatus = 0`) `Job Card`s at the mapped work centre whose `Work Order`
   has `exec_state == "In Progress"`, in routing sequence, filtered by the mapping's operation
   when pinned. No candidate ⇒ queued;
3. **attach** an `OPC UA Tracking Event` with `source_system = "OPC-UA"`, the equipment
   timestamp *and* the MES receipt time, sequence, value in kg, `is_late`, work centre, line,
   order, operation and job card;
4. **drive W1** — a start/stop signal starts/stops the card's time log through
   `manufacturing_core.shopfloor.job_execution`; a signal the card cannot honour (stop
   without a running log) leaves the event recorded and the refusal in the audit detail;
5. **audit** through `execution_gating.audit.log_transition` at gate `OPC-UA Ereignis`;
6. record `processing_seconds` — the 5 s attachment budget of AC-1 is measured, not assumed.

### D3 — The source system is the actor, never an operator

The whole ingestion runs inside `ingest.as_source_system()`, which switches the session to the
service account `opcua@rheinwerk-chemie.example` (role `Rheinwerk SCADA Adapter`, installed by
`setup/w3_scada.py`) and restores the previous user afterwards. Time logs are written without
an `employee`, so machine-reported work is never credited to a person. Offline unit runs
without the account fall back to the current user — the attribution *stored on the event* does
not depend on the session.

### D4 — Cumulative output is booked when the operation stops

W1 `record_output` **sets** the card's completed quantity and closes the running time log, so
booking every single count would shred the operator's time record. The adapter therefore books
the *cumulative* OPC-UA count (`sum(value)` over processed/assigned counts up to the event's
equipment time) when the operation stops, and immediately for a count that arrives late for an
already stopped operation. Genealogy is reconciled straight after through
`genealogy.links.rebuild_links_for_work_order`, so the trace reads the quantities the
equipment reported.

## 4. Unmatched queue (URS-W3-015 AC-2)

Nothing is dropped: an unmapped tag or a work centre without an In-Progress order produces a
tracking event in state `Nicht zugeordnet` carrying `unmatched_reason`, plus its own audit
entry. `rheinwerk_mes/integration/page/scada_unmatched_events` (Desk page
"Nicht zugeordnete OPC-UA-Ereignisse") lists them with tag, work
centre, equipment time (DD.MM.YYYY HH:mm:ss), quantity in kg and a late badge, and offers

* **Auftrag zuordnen** → `unmatched.assign_to_order(event, work_order, note)`: re-matches the
  event against the chosen order's job card at that work centre, state `Zugeordnet`, audited;
* **Verwerfen** → `unmatched.discard(event, note)`: state `Verworfen` with a **mandatory**
  note, audited.

Rows are never deleted — a discarded event stays readable, which is what makes the queue an
audit trail rather than an inbox.

## 5. Store-and-forward (URS-W3-017)

`SpoolBuffer` is a JSON-lines file on the adapter side: `append()` writes one line and
`fsync`s it, so an event survives a crash between equipment and MES. `ScadaAdapter.publish()`
spools instead of ingesting while `connected` is false; `connect()` calls `replay()`, which
drains the spool **oldest first** and ingests every event with `late=True`.

### D5 — The spool is only cleared after the consumer accepted every event

`SpoolBuffer.drain()` deletes the file after its generator is exhausted, so an exception
raised by ingestion mid-replay leaves the spool intact and the events are re-offered on the
next reconnection. At-least-once delivery is preferred over losing an event.

Replayed events keep their original `equipment_timestamp` (only `received_at` is the MES clock)
and are flagged `is_late = 1`; live events are not. Ordering is the spool's FIFO order, which
is the equipment's order.

## 6. Installation, roles, i18n

`setup/w3_scada.py` (idempotent, `after_install` + `patches.txt`) creates the
`Rheinwerk SCADA Adapter` role and its service user, and the DocPerms for adapter,
technologist and planner. `fixtures/seed.py::seed_scada_tag_mappings` seeds the four LINE-1
mappings the simulator publishes on.

All user-facing text goes through `frappe._()` / `__()`, dates render DD.MM.YYYY, quantities
kg; tag addresses, work-centre codes and order numbers render in IBM Plex Mono with tabular
numerals per `rheinwerk-mes-design-SKILL.md`.

The DocTypes and the Desk page live under `rheinwerk_mes/integration/doctype/**` and
`rheinwerk_mes/integration/page/**` because Frappe resolves them from the module directory
(`Integration`); the adapter logic they use stays in `integration/scada/**`.

## 7. Traceability

| URS | Behaviour | Tests |
|---|---|---|
| URS-W3-015 | ingestion, matching, OPC-UA attribution, 5 s budget, unmatched queue | `test_w3_scada_ingestion.py` (TC-W3-018) |
| URS-W3-016 | technologist tag mapping, invalid-work-centre refusal | `test_w3_scada_mapping.py` (TC-W3-019) |
| URS-W3-017 | outage buffering, ordered replay, original timestamps, late flag | `test_w3_scada_store_and_forward.py` (TC-W3-020) |
| URS-W3-021 | every event audited at gate `OPC-UA Ereignis` with the source system as actor | `test_w3_scada_ingestion.py` |
