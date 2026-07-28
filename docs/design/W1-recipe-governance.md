# W1-4 — Recipe governance (`gov_state`)

Design note for backlog item **W1-4** (URS-W1-014 … URS-W1-017), module track
`recipe_isa88`. It documents how the Qcadoo *technology* lifecycle is re-expressed on the
ERPNext anchors, which validators run when, and the read helper other W1 children consume.

Related decisions: `docs/adr/ADR-006-canonical-recipe.md`,
`docs/canonical-model/README.md` (CDM-04), `docs/urs/URS-W1-production-core.md` §3.4,
`docs/test/TST-W1-production-core.md` (TC-W1-015 … TC-W1-018, TC-W1-030).

## 1. Model — the governed anchor pair (CDM-04)

Qcadoo models one entity, `technologies_technology`, that carries the operation tree, the
material inputs *and* the lifecycle state. ERPNext splits the same information across two
anchor DocTypes: `BOM` (materials, operations, costing) and `Routing` (reusable operation
sequence). Per ADR-006 the split is kept and **neither anchor is forked**; the *pair* is
governed by a new app-owned DocType:

```
 Item ──< BOM (anchor) ──> Routing (anchor)
             │  1:1
             ▼
   Recipe Governance (rheinwerk_mes, Recipe ISA88 module)
     bom (Link BOM, unique, set_only_once)   → the record's own name
     item (fetched from BOM)                 → successor/predecessor grouping
     routing (Link Routing)
     gov_state (Select: Draft/Checked/Accepted/Outdated/Declined)
     in_use_lock (Check) + in_use_orders     → URS-W1-017 evidence
     validator_results (Table: Recipe Validator Result)
     validated_by / validated_on
     transition_reason + state_history (Table: Recipe Governance State Change)
```

Anchor-side artefacts, all created by the committed installer
`rheinwerk_mes/setup/w1_recipe_gov.py`:

| Artefact | Purpose |
|---|---|
| Custom Field `BOM.rw_gov_state` (read-only, `allow_on_submit`) | the `gov_state` pill on the recipe itself; grouped under the Manufacturing Core module, the W0 convention for anchor Custom Fields (TC-W0-007) |
| `doctype_js` `BOM` → `recipe_isa88/bom_gov_state.js` | renders the pill (icon + label + colour) and a shortcut to the governance record |
| `doc_events` on `BOM` (`validate`, `before_update_after_submit`, `before_cancel`) | change control: immutability + in-use lock |
| `Workflow` "Rheinwerk Rezeptfreigabe" | the `gov_state` transition set with a role on every transition |

The installer is idempotent and runs both from `after_install` (fresh site) and from the
`patches.txt` entry `rheinwerk_mes.setup.w1_recipe_gov` (existing sites).

## 2. Lifecycle (URS-W1-014)

Baseline: Qcadoo `TechnologyState.java:33-66`. The state vocabulary is the target
glossary's (Draft/Checked/Accepted/Outdated/Declined), the transition set is Qcadoo's.

| From | To | Allowed | Notes |
|---|---|---|---|
| Draft | Checked | yes | structural validators run |
| Draft | Accepted | yes | Qcadoo permits the direct release; validators run |
| Draft | Declined | yes | reason required |
| Checked | Draft | yes | rework; reason required |
| Checked | Accepted | yes | validators run; predecessor is outdated afterwards |
| Checked | Declined | yes | reason required |
| Accepted | Outdated | yes | in-use lock applies; reason required |
| Accepted | Draft / Checked / Declined | **no** | released recipes are never rewound (URS-W1-014 AC-3) |
| Outdated | anything | **no** | terminal |
| Declined | anything | **no** | terminal |

Enforcement lives in the DocType controller
(`rheinwerk_mes/recipe_isa88/doctype/recipe_governance/recipe_governance.py`), so a Desk
workflow action, `governance.transition(...)` and a data import all behave identically. The
Frappe `Workflow` publishes the same table with `Rheinwerk Technologist` (plus
`System Manager`) on every transition, and the controller re-checks the role, so the gate is
per transition rather than per DocType (URS-W1-029): a warehouse clerk with read access can
never accept a recipe.

Every transition appends a `Recipe Governance State Change` row (from/to, user, timestamp,
reason) — the change-control record the dossier requires for recipe releases.

## 3. Validator battery (URS-W1-015)

Baseline: `TechnologyValidationService.java:91-707`, ordered as
`TechnologyValidationAspect.java:72-141` applies it. Re-implemented in
`rheinwerk_mes/recipe_isa88/validators.py` as a **pure function over a plain mapping**, so
it runs offline and is directly comparable to the W0 characterisation fixtures.

| # | Validator id | Message key | Qcadoo baseline | Anchor scope |
|---|---|---|---|---|
| 1 | `technology_tree_set` | `…validate.global.error.emptyTechnologyTree` | `checkIfTechnologyTreeIsSet` (`:230-264`) | BOM has no operations and its routing none either |
| 2 | `in_component_quantities` | `…validate.global.error.inComponentsQuantitiesNotFilled` | `checkIfEveryInComponentsHasQuantities` (`:91-144`) | a BOM line without `qty` |
| 3 | `operation_input_components` | `…validate.global.error.noInputComponents` | `checkIfEveryOperationHasInComponents` (`:186-228`) | BOM completeness: no component lines / a line without an item |
| 4 | `final_product_declared` | `…validate.global.error.noFinalProductInTechnologyTree` | `checkTopComponentsProducesProductForTechnology` (`:266-293`) | the BOM's `item` must be the declared output |
| 5 | `operation_tree_units` | `…operationDetails.validate.error.UnitsNotMatch`, `…OutputUnitsNotMatch`, aggregate `…validate.error.OperationTreeNotValid` | `checkIfTreeOperationIsValid` (`:546-580`), `checkIfUnitMatch` (`:618-639`), `checkIfUnitsInTechnologyMatch` (`:641-676`) | production unit set and equal to the output item's stock UoM (mass in kg) |
| 6 | `component_unit_convertible` | `rheinwerk.recipe.validate.error.componentUnitNotConvertible` | *target-only* (see §6) | a BOM line's UoM needs an item-level conversion (URS-W0-004) |
| 7 | `not_used_in_active_order` | `…technology.state.error.orderInProgress` | `checkIfTechnologyIsNotUsedInActiveOrder` / `TechnologyService.isTechnologyUsedInActiveOrder` (`:159-172`) | Work Orders referencing the BOM in an active state |

Ordering and short-circuiting are part of the contract: validators 2 and 3 return
immediately (as the legacy aspect does), and validator 5 appends the aggregate
`OperationTreeNotValid` after the individual unit errors. `CHAR-TECH-VALIDATE-01` compares
the verdict *and* the ordered message keys, so any drift fails the parity leg.

**Snapshot mapping.** `governance.recipe_snapshot(bom, routing)` builds the mapping from the
live anchors: each routing/BOM operation becomes one operation component, BOM lines become
its inputs (attached by the line's `operation` where the anchor records one, otherwise to
the first operation), the BOM `uom` is the production unit and the output item's `stock_uom`
the output unit. Because the anchor keeps materials on the BOM rather than per operation,
every operation after the first is modelled as consuming its predecessor's output (the
semi-finished product) — exactly how the Qcadoo tree passes quantities between operation
components.

**Where they fire.** Validators 1-6 gate `Draft/Checked → Checked` and
`… → Accepted`; validator 7 gates `→ Outdated` and `→ Declined` (the in-use lock, §5) and is
therefore *not* blocking on acceptance. Results are written to `validator_results` on the
governance record on both paths — including the refused one, where they are persisted
explicitly because `frappe.throw` unwinds the save (URS-W1-015 AC-3).

## 4. Immutability and versioning (URS-W1-016)

* An Accepted recipe is immutable. The anchor's own submit lock already refuses field edits
  on a submitted BOM; the governance hook adds the governance-aware refusal and closes the
  cancel-and-rewrite route (`before_cancel`), naming the state and the versioning path.
* A change therefore lands as a **new anchor BOM version** (`BOM-RW-CHM-0003-002`, the
  anchor's own versioned naming) with its own governance record starting in Draft.
* Accepting the successor moves every other Accepted record for the same item to Outdated,
  with `Ersetzt durch Rezeptversion …` as the recorded reason. Outdated is terminal, so the
  predecessor can never be revived — a later change is again a new version.

## 5. In-use lock (URS-W1-017)

`governance.active_orders_for_recipe(bom)` lists Work Orders (docstatus < 2) referencing the
BOM whose state is active. The canonical signal is the `exec_state` extension owned by the
state-machine sibling (`Accepted`, `In Progress`, `Interrupted`); the anchor `status`
reflection (`Not Started`, `In Process`) is accepted as well, so the lock also holds on a
site where `exec_state` is not installed yet. Effects:

* `→ Outdated` and `→ Declined` are refused, naming the locking orders (e.g. `PO-2026-0001`);
* accepting a successor is refused while the predecessor it would outdate is locked;
* modifying/cancelling the anchor BOM is refused while the recipe is in use;
* `in_use_lock` / `in_use_orders` are refreshed on every save, so the lock is visible.

Once the order is Completed the lock disappears and the outdating (via an accepted
successor) succeeds.

## 6. Ambiguity decisions

1. **Direct Draft → Accepted.** Qcadoo allows it (`TechnologyState.java:33-66`), while the
   URS headline reads Draft → Checked → Accepted. The legacy transition set wins (the URS
   AC only requires that the stepwise walk succeeds), and the validators run either way, so
   nothing is released unvalidated.
2. **Pending orders do not lock.** Qcadoo's active-order query includes `01pending`;
   URS-W1-017 scopes the lock to `Accepted`, `In Progress`, `Interrupted`. The URS wins.
3. **Per-operation input completeness.** Qcadoo demands inputs on every operation
   component. On the anchor, materials hang off the BOM, so the check is applied as BOM
   completeness plus the predecessor-output handover described in §3 — a component-less BOM
   still fails, an ordinary two-operation recipe does not.
4. **Target-only validator 6.** Qcadoo products carry a single unit, so a line unit that
   cannot be converted is inexpressible there. On the anchor it is a real failure mode and
   URS-W1-015 AC-1 asks for exactly that refusal, so a target-only message key
   (`rheinwerk.recipe.validate.error.componentUnitNotConvertible`) was added rather than
   overloading a legacy one — the parity fixtures stay untouched and green.
5. **Reason required for Declined / Outdated / rework-to-Draft.** Retiring or rejecting a
   released recipe is change-controlled, so the transition is refused without a reason. The
   reason is stored in the state-history row.
6. **Anchor Custom Field module.** `BOM.rw_gov_state` is registered under the
   Manufacturing Core module because TC-W0-007 pins anchor Custom Fields to that module;
   the governance DocTypes themselves live in Recipe ISA88.

## 7. Read helper for sibling children

```python
from rheinwerk_mes.recipe_isa88.governance import gov_state, is_accepted

gov_state("BOM-RW-CHM-0003-001")     # "Draft" | "Checked" | "Accepted" | "Outdated" | "Declined" | ""
is_accepted("BOM-RW-CHM-0003-001")   # True only in Accepted
```

`gov_state` returns `""` for an ungoverned BOM, so a caller can distinguish "not governed
yet" from "still in Draft". The execution-gating child uses `is_accepted` for URS-W1-006
(order acceptance requires an Accepted recipe). Also available:
`governance_name(bom)`, `can_change(current, target)`,
`active_orders_for_recipe(bom)`, `recipe_snapshot(bom, routing)` and
`evaluate_recipe(bom, routing)`.

The parity entrypoint the W0 harness resolves is
`rheinwerk_mes.manufacturing_core.contracts.evaluate_technology` — a thin adapter over
`recipe_isa88.validators.evaluate_technology`.

## 8. Design conformance

German-first labels, all user-facing strings through `frappe._()` with positional
placeholders (never concatenation), masses in kg, dates DD.MM.YYYY (Frappe system format).
The `gov_state` pill is rendered with icon + label + colour — never colour alone — using the
signal palette: Draft grey, **Checked amber** (hold), **Accepted green** (released),
Outdated grey (inverse), **Declined red** (stop).

## 9. Traceability

| URS | Requirement | TC | Test |
|---|---|---|---|
| URS-W1-014 | `gov_state` workflow, role-gated | TC-W1-015 | `tests/acceptance/test_w1_recipe_gov_lifecycle.py` |
| URS-W1-015 | structural validators at Checked→Accepted | TC-W1-016 | `tests/acceptance/test_w1_recipe_gov_validators.py` |
| URS-W1-015 | Qcadoo parity of the battery | TC-W1-030 (`CHAR-TECH-VALIDATE-01`) | `tests/acceptance/test_w1_recipe_gov_validators.py`, `tests/characterisation/test_contracts.py` |
| URS-W1-016 | Accepted immutable, successor versioning | TC-W1-017 | `tests/acceptance/test_w1_recipe_gov_versioning.py` |
| URS-W1-017 | in-use lock | TC-W1-018 | `tests/acceptance/test_w1_recipe_gov_in_use_lock.py` |
| URS-W1-029 | per-transition role gating | TC-W1-015 | `tests/acceptance/test_w1_recipe_gov_lifecycle.py` |

Evidence: screenshots of BOM-RW-CHM-0003-001 showing the `gov_state` pill and of the
governance record with its stored validator results are attached to the W1-4 PR.
