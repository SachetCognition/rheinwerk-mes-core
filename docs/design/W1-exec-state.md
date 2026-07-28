# W1-1 — production-order `exec_state` machine

**Backlog:** W1-1 · **Requirements:** URS-W1-001…URS-W1-004 · **Test cases:** TC-W1-001…TC-W1-005
**Code:** `rheinwerk_mes/manufacturing_core/exec_state.py`, `rheinwerk_mes/setup/w1_exec_state.py`
**Legacy baseline (semantics only, never ported):** `SachetCognition/Chem_mes@master` —
`orders/states/constants/OrderState.java:31-81`, `orders/model/orderStateChange.xml:36-47`,
`orders/model/reasonTypeOfChangingOrderState.xml`, `orders/states/OrderStateService.java:47-59`.

This note is the contract the sibling W1 children build on: the states, the transition
table, the gate-hook mechanism and the `state_history` schema.

## 1. States

`exec_state` is a Custom Field (`Select`, module *Manufacturing Core*) on the **anchor**
`Work Order`, carried by the Frappe workflow `Production Order Execution`
(`workflow_state_field = exec_state`). The anchor DocType is never forked; the anchor's
own posting-derived `status` stays untouched and is never surfaced unqualified
(ADR-004: only `exec_state`, `qa_state`, `gov_state`).

| State | German pill | Meaning |
|---|---|---|
| `Pending` | Offen | initial state of every order (`before_insert` hook) |
| `Accepted` | Angenommen | planner accepted; anchor document submitted |
| `In Progress` | In Arbeit | execution running |
| `Completed` | Abgeschlossen | terminal |
| `Interrupted` | Unterbrochen | paused, resumable |
| `Abandoned` | Abgebrochen | terminal |
| `Declined` | Abgelehnt | terminal |

## 2. Transition table (exact Qcadoo `canChangeTo` parity)

| From | To | Action | Allowed role |
|---|---|---|---|
| Pending | Accepted | Accept | Rheinwerk Planner |
| Pending | In Progress | Start | Rheinwerk Planner |
| Pending | Declined | Decline | Rheinwerk Planner |
| Accepted | In Progress | Start | Manufacturing User |
| Accepted | Declined | Decline | Rheinwerk Planner |
| In Progress | Completed | Complete | Manufacturing User |
| In Progress | Interrupted | Interrupt | Manufacturing User |
| In Progress | Abandoned | Abandon | Rheinwerk Planner |
| Interrupted | In Progress | Resume | Manufacturing User |
| Interrupted | Abandoned | Abandon | Rheinwerk Planner |

`Completed`, `Declined` and `Abandoned` are terminal — every outgoing transition is
refused. Any other ordered pair is refused with a German message naming the illegal
transition, the order and the legal targets. The table lives in
`exec_state.LEGAL_TRANSITIONS` and is asserted state-for-state against the transcribed
Java `canChangeTo` set in `tests/acceptance/test_w1_exec_state_transitions.py` (all 49
ordered pairs), which also re-runs the W0 characterisation registry so the harness
contracts keep passing against the target implementation.

**Ambiguity resolved:** `docs/design/LLD.md` §2.2 names the approver role
`MES Order Approver`, which does not exist in the estate. W1-1 uses the W0 programme role
`Rheinwerk Planner` (persona P. Krüger, `rheinwerk_mes/setup/roles.py`) for the approver
transitions and the ERPNext `Manufacturing User` role (persona O. Weber) for the operator
transitions; `MES Order Approver` is treated as the design-note alias of `Rheinwerk
Planner`.

## 3. Transition entrypoint

```python
from rheinwerk_mes.manufacturing_core.exec_state import transition

transition(work_order, target_state, reason=None)   # work_order: name or Document
```

`transition()` is the **single** entrypoint (also whitelisted for the Desk). It sets
`exec_state` and saves; every save — from `transition()`, from the Desk workflow bar or
from any other server-side caller — funnels through
`exec_state.validate_exec_state_change`, registered on the anchor as `validate`
(draft) and `before_update_after_submit` (submitted), which in order:

1. refuses illegal transitions (§2),
2. refuses transitions whose workflow row names a role the user does not hold,
3. runs the registered gate callbacks (§4),
4. appends the `state_history` row (§5).

Because the check hangs off the document event, a state change can never bypass the
gates — there is no "back door" write path other than an explicit `db_set`, which is
used by fixtures/tests only.

## 4. Gate-hook contract (what W1-2 plugs into)

Gates are registered **in the app's `hooks.py`**, never by editing this module:

```python
# rheinwerk_mes/hooks.py
rheinwerk_exec_state_gates = [
    "rheinwerk_mes.manufacturing_core.exec_state.reason_gate",        # URS-W1-003
    "rheinwerk_mes.manufacturing_core.exec_state.anchor_submit_gate", # URS-W1-004 AC-1
    "rheinwerk_mes.manufacturing_core.exec_state.shortfall_gate",     # URS-W1-004 AC-2
    # W1-2 appends its acceptance / completion / material-availability gates here
]
```

Execution order is the hook order (app order, then declaration order), so the three core
gates above always run first. A gate is a callable taking a `TransitionContext`:

```python
@dataclass
class TransitionContext:
    doc: Document          # the anchor Work Order being transitioned
    from_state: str
    to_state: str
    reason: str | None     # a gate may set this to persist a different audit reason
    errors: list[str]      # append German-first refusal messages here
```

A gate either

* appends messages to `context.errors` (or returns an iterable of messages) — all
  collected messages are raised together as **one** modal titled
  "Übergang abgelehnt: {from} → {to}" (design skill § "Hard gates look hard": rule,
  record, resolution), or
* throws its own `frappe.throw(...)` when it wants full control of the modal.

Gates must be side-effect free: they judge, they do not post. Side effects belonging to a
transition (e.g. releasing reservations on Decline/Abandon, URS-W1-009) belong in a
`Work Order` document event that reads the freshly written `state_history` row.

## 5. `state_history` schema

Child table `Order State History` (W0 container, extended in W1-1 with `reason`),
mounted on the anchor as the read-only, `allow_on_submit` table field `state_history`:

| fieldname | fieldtype | notes |
|---|---|---|
| `from_state` | Data | state before the transition |
| `to_state` | Data | state after the transition (mandatory) |
| `changed_by` | Link User | `frappe.session.user` at transition time |
| `changed_at` | Datetime | server time |
| `reason` | Small Text | mandatory for Declined, Abandoned, Interrupted; also carries the completion shortfall reason |
| `remarks` | Small Text | free text (W0 container field) |

Read it with `exec_state.state_history(work_order)` (oldest first).

## 6. Reconciliation with the anchor (URS-W1-004)

* **Accept requires anchor submit** — accepting a Work Order in docstatus 0 is refused
  (`anchor_submit_gate`).
* **Completion requires produced ≥ ordered, or an explicit shortfall reason** — the
  anchor's own `status` reaching *Completed* never auto-completes `exec_state`
  (`shortfall_gate`); the shortfall reason is persisted in `state_history.reason` and may
  be supplied through the `shortfall_reason` field or the `reason` argument.
* **Anchor hard stops stay untouched** (over-production, stopped/closed orders — W1-3).
* **Vocabulary:** no `rheinwerk_mes` field or label uses the unqualified word "status";
  the W0 audit-table labels were renamed to "Von Zustand" / "Nach Zustand" and the table
  label to "Ausführungsverlauf". German compounds such as *Statusverlauf* are not the
  unqualified word, but they were removed anyway so the scan in
  `test_w1_exec_state_vocabulary.py` can stay a simple word-boundary check.

## 7. Installation

`rheinwerk_mes/setup/w1_exec_state.py` creates the Custom Fields, the Workflow (states,
actions, transitions, pill styles) and backfills `exec_state = Pending` on existing
orders. It runs from `install.after_install` (fresh site) and from the `patches.txt`
entry `rheinwerk_mes.setup.w1_exec_state` (existing sites); it is idempotent.
