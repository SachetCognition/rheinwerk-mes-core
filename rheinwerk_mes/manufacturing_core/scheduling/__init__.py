"""Finite-capacity scheduling layer (W3-2 · URS-W3-005 … URS-W3-009).

The layer sits *over* the anchor: production orders stay anchor `Work Order` documents
carrying the W1 `exec_state`, work centres stay anchor `Workstation` records with their
`production_capacity`, and the capacity refusal reuses the anchor's own `CapacityError`.
What W3-2 adds — line schedules with their own governed state, TJ/TPZ realization times and
line changeover norms — lands as new DocTypes owned by `rheinwerk_mes` plus the pure
calculators in this package (`docs/design/W3-finite-capacity.md`).

Public surface:

* `schedule_state` — the Draft → Approved / Rejected machine (Qcadoo `ScheduleState` parity).
* `realization_time` — TJ/TPZ arithmetic, minute-exact against the legacy baseline.
* `changeover` — line changeover-norm lookup with Qcadoo's specificity precedence.
* `sequencing` — pure sequencing of a line's orders including changeover insertion.
* `capacity` — the retained anchor slot search and its gate refusal.
* `lifecycle` — schedule creation, approval and rejection with audit.
* `board` — the whitelisted read API behind the schedule board page.
* `contracts` — pure parity entrypoints consumed by the W0-6 characterisation harness.
"""
