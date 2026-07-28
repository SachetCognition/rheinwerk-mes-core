# W1-7 / W1-8 — Shop-floor operator journey and role model

Design record for the shop-floor half of Wave 1: the operator journey on the anchor
`Job Card` (W1-7, URS-W1-026…028 plus the interface NFRs URS-W1-022, URS-W1-032, -034,
-035) and the workflow-state-level role model (W1-8, URS-W1-029).

Related records: `docs/design/W1-exec-state.md` (the `exec_state` machine this journey
feeds), `docs/urs/URS-W1-production-core.md`, `docs/test/TST-W1-production-core.md`,
`rheinwerk-mes-design-SKILL.md`.

## 1. Substrate decisions

| Concern | Decision | Why |
|---|---|---|
| Job cards | **Adopt** the anchor `Job Card` unchanged (`job_card.py:1280-1397`) | It already models per-operation execution, time logs, `is_paused`/On Hold and the submission completeness rules (`:912-959`). Forking it would fork the manufacturing substrate. |
| Time logs | Anchor `time_logs` child table | One truth for durations; the operator API only opens and closes rows. |
| Pause | Anchor `Job Card.pause_job` | Substrate keeps owning `is_paused` and status derivation. |
| Resume | Re-expressed in `shopfloor.job_execution.resume_job` | The anchor's `resume_job` iterates the Employee multi-select; the shop-floor terminal works cards without an Employee record, so the same semantics (clear `is_paused`, open a fresh log, back to Work In Progress) are expressed directly on the anchor fields. |
| Output | Recorded on the card, submitted through the anchor | Completion stays the anchor's rule set — including the On Hold refusal (URS-W1-027 AC-2). |
| Extensions | Custom Fields `Workstation.station_profile`, `Job Card.rw_scan_code`; new DocType `Transition Refusal Log` | No anchor fork; installed idempotently by `rheinwerk_mes/setup/w1_shopfloor.py` and `w1_roles.py` (`after_install` + `patches.txt`). |

## 2. Operator journey

```
scan PO-2026-0001 ──► job_queue()  ──► Terminal Card (MIX)
                                    │  start_job → time log opens
                                    │  pause_job → On Hold, log closed
                                    │  resume_job → new log, Work In Progress
                                    └► record_output(500, submit) → anchor submit
                                              │
                                              └► order_output() feeds the
                                                 exec_state completion gate
```

`order_output()` reports the **last** operation's booked quantity as the order's recorded
output (earlier operations feed it and must not be double-counted), which is what
URS-W1-004's completion gate compares with the ordered quantity.

## 3. Interface rules made testable

| Rule | Implementation | Test |
|---|---|---|
| Scanner is first-class (URS-W1-028) | `shopfloor/scanner.py` resolves Work Order → Job Card → Batch → Item and always answers; unknown codes return a focused inline error. `shop_floor_terminal.js` keeps focus on blur and confirms audibly. | `test_w1_shopfloor_scanner.py` |
| Latency budget (URS-W1-032) | Scan resolution is a single indexed existence check per target and reports its own `server_ms`; the page shows busy state on the control and renders results only after the server answers. | `test_w1_shopfloor_latency.py` (100 sequential scans, p95 ≤ 300 ms) |
| German-first (URS-W1-034) | `shopfloor/formatting.py` is the only place dates (DD.MM.YYYY) and masses (kg) are rendered; every user-facing string passes `frappe._()` or the `_lazy()` message-id marker. | `test_w1_shopfloor_i18n.py` (AST scan of the W1-7 footprint + the page asset) |
| Density modes (URS-W1-035) | `shopfloor/terminal.py` holds the tokens (Desk 14/32/32 px, Terminal 18/56/48 px) and the shared field list; `public/css/shopfloor.css` mirrors them; mode auto-selects from `Workstation.station_profile` and toggles with F2. | `test_w1_shopfloor_density.py` |
| Legacy bridge (URS-W1-022) | `shopfloor/legacy_bridge.py` maps renamed fields to their Qcadoo/OFBiz names and writes them as Property Setter descriptions; `set_enabled(False)` strips them after cutover. | `test_w1_shopfloor_legacy_bridge.py` |

Manual residue (recorded in each test's docstring, evidenced by the delivery-PR
screenshots): the audible tone on plant hardware, the browser-side sub-100 ms paint, and
the grayscale review of the rendered pills.

## 4. Role model (W1-8)

Qcadoo gates state changes per transition, not per entity. The matrix lives in
`rheinwerk_mes/setup/w1_roles.py` and is written into the Workflow Transition rows that
`exec_state._assert_role_allowed()` already enforces:

| Transition | Allowed |
|---|---|
| Pending → Accepted / Declined, Accepted → Declined | Planner |
| Pending → In Progress | Planner |
| Accepted → In Progress, In Progress → Completed / Interrupted, Interrupted → In Progress | Planner, Shop Floor Operator |
| In Progress → Abandoned, Interrupted → Abandoned | Planner |
| `gov_state`: Draft → Checked → Accepted, Accepted → Outdated, Draft → Declined | Technologist |

Two new roles are created from code: **Rheinwerk Shop Floor Operator** (write on Job Card,
read elsewhere) and **Rheinwerk Business Viewer** (read-only, sees the audit). The seeded
personas O. Weber and B. Vogel receive them at install time.

The `gov_state` rows are applied only once the W1-4 `Recipe Governance` workflow exists on
the site; the matrix is committed now so the transition roles land with that workflow
rather than after it.

### Refusal audit

Every refused transition is written to the new `Transition Refusal Log` (reference,
from/to state, user, timestamp, allowed roles, message). The DocType grants no write or
delete right to any role and its controller refuses both, so the audit is append-only —
the compliance record URS-W1-029 AC-3 and URS-W1-033 require. Terminal actions call
`shopfloor/transitions.request_transition()`, which delegates to the state machine and
writes the audit row on refusal; the state machine itself is untouched.

## 5. Open points

* `gov_state` transition roles are inert until W1-4 installs the `Recipe Governance`
  workflow (the mapped test skips, never fails, on a site without it).
* Terminal hardware profiles are represented by a single `station_profile` field; a richer
  station registry (per-terminal shortcuts, printer bindings) is out of W1 scope.
