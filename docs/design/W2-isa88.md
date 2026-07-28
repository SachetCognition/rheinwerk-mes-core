# W2-6 — ISA-88 batch recipes + scaling (`recipe_isa88`)

Design note for backlog item **W2-6** (URS-W2-020 … URS-W2-022), module track
`recipe_isa88`. It documents how the ISA-88 procedural hierarchy is layered over the
governed anchor BOM + Routing pair *without forking either anchor*, how a recipe is scaled
to an order quantity with `Decimal`-exact arithmetic, and how the scaled recipe re-enters
the existing W1-4 `gov_state` governance.

This capability is **white space in all three legacy systems** (dossier §6.3, ch. G
"ISA-88: Absent" ×3): there is no Qcadoo behaviour to absorb and no parity contract to
satisfy. The model below is designed from the URS and the ISA-88 (IEC 61512-1) vocabulary.

Related: `docs/design/W1-recipe-governance.md` (the `gov_state` layer this extends),
`docs/adr/ADR-006-canonical-recipe.md`, `docs/canonical-model/README.md` (CDM-04),
`docs/urs/URS-W2-traceability-quality.md` §3.6, `docs/test/TST-W2-traceability-quality.md`
(TC-W2-028 … TC-W2-030).

## 1. What "no anchor fork" means here

Per ADR-006/CDM-04 the recipe is the **governed pair** `BOM` (materials, costing) +
`Routing` (operation sequence). ISA-88 adds a *procedural* view on top: the recipe is a
**procedure** made of **unit procedures**, each made of **phases**. None of that structure
belongs on the anchor DocTypes, so it lives entirely in three app-owned DocTypes in the
`Recipe ISA88` module that **reference** the anchors:

```
 Item ──< BOM (anchor) ──> Routing (anchor)          ← governed by Recipe Governance (W1-4)
             ▲
             │ Link (unique, set_only_once)
   ISA88 Recipe (rheinwerk_mes, Recipe ISA88)
     ├─ unit_procedures : ISA88 Unit Procedure[]  → each binds one Routing operation + work centre
     └─ phases          : ISA88 Phase[]           → material charge / process step, grouped by unit procedure
```

The only anchor-side artefact W2-6 adds is one **Custom Field on `Workstation`**
(`rw_max_working_qty`, the equipment working-volume ceiling used by scaling), created
idempotently by the committed installer `rheinwerk_mes/setup/w2_isa88.py`. `BOM`, `Routing`
and their child tables keep their `erpnext` schema unchanged (asserted by TC-W2-028 step 2 /
URS-W2-020 AC-2, alongside the standing TC-W0-007 anchor-fork guard).

## 2. Hierarchy mapping (URS-W2-020)

| ISA-88 (IEC 61512-1) | Rheinwerk model | Anchor binding |
|---|---|---|
| Procedure | `ISA88 Recipe` (one per BOM version) | `bom` (unique Link), `routing` |
| Unit procedure | `ISA88 Unit Procedure` row | `operation` (Link Routing `Operation`) + `workstation` (Link `Workstation`, the work centre) |
| Operation | *collapsed onto the Routing operation* — see decision D1 | the unit procedure's `operation` |
| Phase | `ISA88 Phase` row (`unit_procedure` grouping key) | optional `material` (Link `Item`) that must be a BOM component |

Worked example (the seeded structured variant of BOM-RW-CHM-0003-001, URS-W2-020 AC-1):

| Unit procedure | Work centre | Phase | Type | Material | Qty |
|---|---|---|---|---|---|
| Mischen | LINE-1 / MIX-01 | Dosieren Basisharz | Dosieren | RW-CHM-0001 | 480 kg |
| Mischen | LINE-1 / MIX-01 | Dosieren Additiv | Dosieren | RW-CHM-0002 | 20 kg |
| Mischen | LINE-1 / MIX-01 | Mischen 30 min | Verarbeiten | — | — (30 min) |
| Abfüllen | LINE-1 / FILL-01 | Abfüllen Gebinde | Abfüllen | — | — |

`batch_size` on the recipe is the **nominal master-batch output** (500 kg here); it is the
ISA-88 recipe's own declared quantity and is deliberately independent of the anchor BOM's
per-batch `quantity` (decision D2). A phase carries `material` only when it charges material;
process phases ("Mischen 30 min") carry a `duration_min` instead.

**Structure validation (URS-W2-020 AC-3).** `ISA88Recipe.validate` (delegating to
`recipe_isa88.structure.validate_structure`) refuses to save when a phase names a `material`
that is not a component line of the linked BOM, naming the phase and the material — so the
procedural view can never reference material the material master does not know. It also
refuses a phase whose `unit_procedure` grouping key names no unit procedure.

## 3. Scaling (URS-W2-021)

`recipe_isa88.scaling.scale_recipe(source, target_batch_size, confirm_rounding=False)`
produces a **new governed recipe version** from an existing one:

1. **Factor** `f = target_batch_size / source.batch_size`, computed in `Decimal` exactly
   like the W0 UoM code (`manufacturing_core/uom.py`) — never binary float. For 500 → 250,
   `f = 0.5`.
2. **Equipment check (URS-W2-021 AC-2).** For each unit procedure the *scaled charge* is the
   sum of its phases' scaled material quantities. If a work centre declares
   `rw_max_working_qty > 0` and the scaled charge exceeds it, scaling is refused with a
   hard-gate message naming the unit procedure (and its representative phase), the work
   centre and the limit. MIX-01 with a 600 kg ceiling refuses a 750 kg scale (720 + 30 kg).
3. **Rounding guard (URS-W2-021 AC-3).** Scaled quantities are quantised to
   `QUANTITY_PRECISION` (2 decimals = 10 g, the kg display precision). If a phase's exact
   scaled quantity is non-zero but quantises to zero (e.g. 0.004 kg), the result is **not
   silently zeroed**: with `confirm_rounding=False` scaling is refused, listing the phase and
   material for technologist confirmation; with `confirm_rounding=True` the quantity is kept
   at full `Decimal` precision (not rounded to zero) and the new recipe carries
   `rounding_confirmation_required = 1` as a visible advisory.
4. **New anchor BOM version.** A new `BOM` for the same item is created from the *scaled phase
   materials* (aggregated by item), with `quantity = target_batch_size`, and submitted. The
   anchor's own versioned naming yields `BOM-RW-CHM-0003-002`, so the scaled recipe is a real
   anchor BOM version — never a fork.
5. **Governance.** A `Recipe Governance` record is created for the new BOM; it starts in
   **Draft** (URS-W2-022 / URS-W2-021 AC-1). The new `ISA88 Recipe` records `source_recipe`
   and `scale_factor` (0.5) and copies the unit procedures with scaled phases.

Mass balance is preserved because every phase quantity and the declared output are scaled by
the *same* factor: `Σ(scaled inputs) = f · Σ(inputs) = f · output = scaled output`. The
`tests/acceptance/test_w2_isa88_scaling.py` suite proves this for a non-integer factor
(0.75: 480 → 360 kg, 20 → 15 kg, output 500 → 375 kg, 360 + 15 = 375) and confirms the scaled
BOM still passes the full W1-4 validator battery.

## 4. Execution under governance (URS-W2-022)

Nothing new is built here — the scaled recipe re-uses the W1-4 machinery unchanged:

* the scaled BOM's governance record is **Draft**, so the existing
  `execution_gating.gates.recipe_accepted_gate` refuses accepting a production order that
  references it, naming the recipe and its `gov_state` (URS-W2-022 AC-1);
* transitioning the record Draft → Checked → Accepted runs the W1-4 structural validators
  against the scaled BOM (they pass — see §3);
* once Accepted, an order referencing the scaled BOM accepts, and the recipe's
  `in_use_lock` (via `governance.enforce_recipe_change_control`) blocks structural edits to
  the anchor BOM while the order is active (URS-W2-022 AC-2).

## 5. Decisions (white-space, no legacy to defer to)

* **D1 — ISA-88 operation tier collapsed onto the Routing operation.** IEC 61512-1 nests
  Operation between Unit procedure and Phase. The anchor already models an operation
  sequence (Routing), so each unit procedure binds one Routing operation and phases hang
  directly off the unit procedure. This keeps a single source of truth for the operation
  sequence (the anchor Routing) and avoids a redundant procedural operation tier. Recorded
  here rather than adding an empty DocType level.
* **D2 — recipe `batch_size` is independent of the anchor BOM `quantity`.** The ISA-88
  recipe declares its own nominal master batch (500 kg); the anchor BOM stays the
  per-`quantity` material master. Structure validation therefore checks material
  *membership* in the BOM, not quantity equality — the two describe the same materials at
  different reference quantities, and scaling always works from the recipe's own
  `batch_size`.
* **D3 — quantity precision = 2 decimals (10 g).** Chosen as the kg carrying precision so
  the rounding guard fires exactly at the URS example (0.004 kg → 0.00). Centralised as
  `scaling.QUANTITY_PRECISION`; the scale factor itself is kept at full `Decimal` precision.
* **D4 — equipment limit lives on the work centre.** `rw_max_working_qty` is a Custom Field
  on the anchor `Workstation` (module `Recipe ISA88`, no `status` token — TC-W1-005 clean),
  because the working-volume ceiling is a property of the equipment, not of a recipe. A
  value of 0/blank means "no declared limit".

## 6. Design conformance

German-first labels, all user-facing strings through `frappe._()` with positional
placeholders (never concatenation), masses in kg with a decimal comma in messages, dates
DD.MM.YYYY. The refusal messages reuse the W1 hard-gate shape (rule / record / resolution)
where they gate an action.

## 7. Traceability

| URS | Requirement | TC | Test |
|---|---|---|---|
| URS-W2-020 | ISA-88 hierarchy over BOM/Routing, anchor unforked, phase-material-in-BOM validation | TC-W2-028 | `tests/acceptance/test_w2_isa88_structure.py` |
| URS-W2-021 | scaling arithmetic, equipment limits, rounding guard | TC-W2-029 | `tests/acceptance/test_w2_isa88_scaling.py` |
| URS-W2-022 | scaled recipe governed (Draft), accept gate, in-use lock | TC-W2-030 | `tests/acceptance/test_w2_isa88_governance.py` |

Evidence: a screenshot of the scaled recipe (source reference + scale factor 0.5 + scaled
phases) is attached to the W2-6 PR.
