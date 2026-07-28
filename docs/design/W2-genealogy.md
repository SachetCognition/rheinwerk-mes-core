# W2-1/2/3 — Genealogie, kanonische Charge und Sperrung

Design note for the genealogy module (`rheinwerk_mes/genealogy/**`), the prerequisite child
of W2. It documents the interfaces the quality (W2-4), CoA (W2-5), hazmat and
warehouse-completion children consume, so none of them has to edit this package.

Implements URS-W2-001 … URS-W2-012 of `docs/urs/URS-W2-traceability-quality.md`; test
coverage TC-W2-001 … TC-W2-017 plus the parity cases TC-W2-040/041.

## 1. Persistence — no anchor fork

Everything hangs off the unmodified ERPNext `Batch` anchor as Custom Fields plus new child
DocTypes owned by `rheinwerk_mes`, installed idempotently by
`rheinwerk_mes/setup/w2_genealogy.py` (`after_install` + `patches.txt`).

| Field on `Batch` | Type | Purpose |
|---|---|---|
| `qa_state` | Select (Quarantined/Released/Blocked) | disposition, workflow-driven (URS-W2-006) |
| `qa_state_reason` | Small Text | reason of the *current* disposition |
| `qty_original` / `supplier_batch_no` | Float / Data | canonical identity facets (URS-W2-005) |
| `genealogy_incomplete` / `trace_boundary_date` | Check / Date | completeness marking (URS-W2-004) |
| `genealogy_links` | Table `Genealogy Link` | produced ↔ used links (URS-W2-001) |
| `blocked_ancestors` | Table `Blocked Ancestor Advisory` | propagated advisories (URS-W2-009) |
| `qa_state_history` | Table `Batch QA State History` | disposition audit (URS-W2-006 AC-2) |
| `legacy_refs` | Table `Legacy Reference` (W0) | **the single** legacy-identifier store (URS-W2-007) |

`Storage Location` gains `is_quarantine_location` (URS-W2-012); `Item` gains `qc_exempt` for
the QC-exempt policy on the Quarantined entry state.

A `Genealogy Link` row is `(direction, batch, item, qty, uom, production_order)` with
`direction ∈ {consumed, produced}` — the Qcadoo `TrackingRecordFields` shape (one produced
batch, n used batches with quantity) expressed on the produced batch itself.

Links are **derived from the postings, never hand-written**: `links.on_stock_entry_submit`
and `.on_stock_entry_cancel` rebuild all rows of the affected work order from its submitted
Stock Entries, so a cancel-and-repost corrects the genealogy in the same transaction and
leaves no stale row (`links.reconcile_work_order(order)` returns the divergences; `[]` means
links and stock ledger agree). Rows whose item is not batch-managed produce no link and do
**not** mark the batch incomplete.

## 2. Trace API (consumed by the Trace Ribbon, CoA W2-5, demo W2-9)

```python
from rheinwerk_mes.genealogy import trace

trace.backward(batch, levels=trace.MAX_LEVELS)  # inputs, suppliers upstream
trace.forward(batch, levels=trace.MAX_LEVELS)   # consumers, deliveries downstream
trace.flatten(tree) -> list[node]
trace.nodes_at_level(tree, n) -> list[node]
trace.ancestors(batch) / trace.descendants(batch) -> list[str]
trace.blocked_ancestors(batch) -> list[str]
```

Both return the same node shape, rooted at `batch` with `level == 0`:

```python
{
    "batch": "BATCH-C-1001", "item": "RW-CHM-0003", "level": 0,
    "qty": 480.0, "uom": "Kg",              # quantity of the edge into the parent, in kg
    "production_order": "PO-2026-0001",
    "qa_state": "Released", "qa_state_label": "Freigegeben",
    "expiry_date": "31.12.2026",             # DD.MM.YYYY, ready to render
    "genealogy_incomplete": False, "trace_boundary_date": None,
    "blocked_ancestors": [], "children": [...],
}
```

Traversal is breadth-first with a `visited` set: cycles terminate, an already expanded node
is not expanded twice (the repeat edge is marked `revisited: True`), depth is capped at
`MAX_LEVELS = 20`. Consumers must treat `children` as the only nesting axis and read `level`
rather than counting recursion depth.

## 3. Disposition API and gate registration

```python
from rheinwerk_mes.genealogy import qa_state

qa_state.transition(batch, target_state, reason=None, triggering_document=None)
qa_state.current_state(batch) / qa_state.state_history(batch)
qa_state.allowed_targets(state) / qa_state.is_legal(from_state, to_state)
```

States and legal edges (Qcadoo `BatchState.java:31-44`, plus the Quarantined entry state
which has no legacy counterpart — deviation signed off under URS-W2-006):

```
Quarantined ──► Released ◄──► Blocked
     └────────► Blocked
```

Every batch is created Quarantined; every transition writes a `Batch QA State History` row
with user, timestamp, from/to state, reason and the triggering document; Blocked and
Released require a reason (the reason of the previous disposition never satisfies the gate);
illegal edges are refused naming the legal targets; the disposition is restricted to the
quality role, which the installer grants Batch write access via a Custom DocPerm.

**Gate registration** mirrors the W1 `exec_state` pattern (`docs/design/W1-exec-state.md`).
Siblings append to the `rheinwerk_qa_state_gates` hook in their own `hooks.py`:

```python
# rheinwerk_mes/hooks.py of the quality child — no edit to the genealogy package
rheinwerk_qa_state_gates = ["rheinwerk_mes.quality.gates.require_accepted_inspection"]

def require_accepted_inspection(context):   # context: qa_state.TransitionContext
    if context.to_state == "Released" and not accepted_inspection(context.doc.name):
        context.refuse(_("Freigabe erst nach angenommener Qualitätsprüfung."))
```

Gates run before the state is written; any `context.refuse(...)` aborts the transition and
the collected messages are raised as one refusal.

## 4. Blocking, picking exclusion, quarantine

```python
from rheinwerk_mes.genealogy import blocking, quarantine

blocking.is_pickable(batch) -> bool          # THE picking-exclusion predicate
blocking.pickable_batches(batches) -> list[str]
blocking.excluded_qty(item, warehouse) -> Decimal
blocking.assert_pickable(batch, handling_unit=None)   # refusal modal + audit log
quarantine.is_quarantine_location(loc) / quarantine.putaway_proposal(batch, warehouse)
```

`is_pickable` is false for Blocked **and** Quarantined stock (`NON_PICKABLE_STATES`) and is
the *only* place that decision is made. `rheinwerk_mes/warehouse/**` consults it in exactly
two spots — `disposal.picking_order_for_warehouse` (proposals) and
`availability.available_qty` (reservations, via `excluded_qty`) — and nothing else in the
warehouse package changed. Qcadoo excluded blocked resources only
(`ResourceCriteriaModifiers.java:59,70`); the additional Quarantined exclusion is the
deviation signed off under URS-W2-006/010.

Blocking a batch propagates a `Blocked Ancestor Advisory` to **every** downstream batch at
every level, naming the blocked ancestor; downstream `qa_state` is untouched (the
disposition stays with quality). Advisories clear when the ancestor is released and no other
blocked ancestor remains. Blocked batches are refused as genealogy input in the UI-facing
predicate and in the server hook (`blocking.enforce_blocked_batch_consumption` on Stock Entry
validate) with the same rule identifier, and every refusal is written to the W1 Execution
Gate Log naming rule, record and resolution.

Quarantine: `putaway_proposal` targets a `is_quarantine_location` location for Quarantined
stock, and `quarantine.enforce_quarantine_exit` refuses movements out of quarantine while
the batch is not Released, or when the user holds neither the quality nor the warehouse-clerk
role.

## 5. Trace Ribbon

`rheinwerk_mes.genealogy.ribbon.ribbon(batch, levels)` (whitelisted) returns the view model
`{focus, left, right, levels, printable}`; `left` is the backward trace, `right` the forward
trace, each chip pre-rendered German-first (labels, DD.MM.YYYY, kg) with `pills`
(`label`+`icon`+`tone` — never colour alone) and `branch_break` for a blocked branch. The
Desk page `trace-ribbon` renders it horizontally (upstream left, focus centred, downstream
right), supports arrow-key selection, Enter to recentre with preserved expansion state, Esc
to close the detail panel, and prints with the blocked break retained in greyscale.

## 6. Deliberate deviations

| Deviation | Legacy baseline | Sign-off |
|---|---|---|
| Quarantined entry state | `BatchState.java:31-44` knows TRACKED/BLOCKED only | URS-W2-006 |
| Quarantined stock also excluded from picking | `ResourceCriteriaModifiers.java:59,70` excludes blocked only | URS-W2-006/010 |
| Advisory propagation downstream | no Qcadoo counterpart | URS-W2-009 |
| Links derived from postings instead of an editable tracking record | Qcadoo tracking records are user-maintained | URS-W2-001 AC-2 |
