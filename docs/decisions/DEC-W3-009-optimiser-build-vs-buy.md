# DEC-W3-009 (D4) — Finite-capacity optimiser: build vs buy

Decision record for **URS-W3-009** (W3-2) and programme dependency **D4** of
`docs/plan/consolidation-project-plan.md` ("Business sign-off Q3: build vs buy for
finite-capacity optimisation?"). It exists so that the *absence* of an optimiser in the
consolidated core is deliberate, dated and traceable rather than an omission — TC-W3-012
audits this file and refuses the wave exit without it.

- **Status:** Accepted — neither build nor buy in W3. Deferred, revisit at the W5 review.
- **Decision:** W3 ships a **norm-based, planner-driven finite-capacity layer** — line
  schedules, TJ/TPZ realization times, changeover norms and the anchor's capacity slot
  search. No constraint solver, no automatic sequence optimisation, no objective function.
- **Sign-off:** Sachet Agarwal — Programme Owner — 28.07.2026
- **Scope verdict:** Won't (recorded exclusion), URS-W3-009
- **Audited by:** TC-W3-012, `tests/acceptance/test_w3_scheduling_scope.py`

## Why a decision was needed

The three systems being consolidated all stop short of optimisation, and the target model's
Q3 asks whether the consolidated core should close that gap:

| Estate | Finite-capacity behaviour | Source |
|---|---|---|
| Plant A — Qcadoo MES | Norms only: TJ/TPZ realization times, line changeover norms, a schedule the planner approves. `ScheduleState` has no optimisation step — sequence is the order the planner puts on the line. | `OrderRealizationTimeServiceImpl.java`, `ScheduleState.java:8-24`, `mes-plugins-line-changeover-norms` |
| Plant B — OFBiz | Infinite capacity; routing times are documentation. | dossier §6.2 |
| Substrate — ERPNext | Sequential slot search per work centre against `Workstation.production_capacity`, refusing with `CapacityError` when no slot is found inside the planning horizon. No optimiser. | `work_order/services/operations.py:105-130` |

The dossier (§6.2) records the estate as it is: *"finite capacity scheduling … still no
optimiser anywhere"*. Introducing one in W3 would therefore be a **new capability**, not a
consolidation of an existing one.

## Options considered

1. **Build** — model the plant as a CP/MIP problem (OR-Tools or similar) and generate
   sequences automatically.
   *Cost:* a solver dependency in a GxP-relevant path, a model that must be validated and
   re-validated per change, planner trust to be earned, and an objective function nobody has
   yet agreed (throughput? changeover minutes? due-date adherence?).
2. **Buy** — integrate an APS product (e.g. an external scheduling suite).
   *Cost:* a second system of record for the plan, a new integration contract and licence,
   directly against the programme's purpose of *reducing* the number of systems.
3. **Neither in W3** — deliver the norm-based layer the estate already runs on, keep the
   planner in control, and keep the door open. **Chosen.**

## Rationale

* **Consolidation first.** W3's mandate is to replace three systems with one governed core.
  Adding a capability none of the three has widens scope and risk in the same wave that
  retires them.
* **No agreed objective.** Optimisation needs a business objective function. None exists;
  D4 asked the question and the answer is that the objective must be established from
  operating data of the consolidated core — data that only exists *after* W3.
* **Validation cost.** A solver's output is hard to explain to an auditor. The norm-based
  layer is arithmetic anyone can reproduce (TPZ + quantity × TJ, plus the changeover norm),
  pinned to the minute by `CHAR-REALIZATION-TIME-01`.
* **The gate that matters is kept.** The genuinely protective behaviour — refusing an
  unplaceable operation — comes from the substrate's slot search and is retained and made
  modal-grade with a named work centre, blocking booking and earliest feasible slot
  (URS-W3-008). That is the safety property; automatic sequencing is convenience.

## What W3 therefore delivers instead

* `Line Schedule` with the Qcadoo `schedule_state` lifecycle (Draft → Approved / Rejected),
  the planner's sequence, and one operative schedule per line.
* Realization times from TJ/TPZ norms per operation and work centre, minute-exact.
* Changeover norms inserted between consecutive orders, with an explicit annotation when no
  norm matches.
* The retained capacity refusal, audited in the `Execution Gate Log`.

## Boundary — what would reopen this decision

* A business-agreed objective function and a target KPI for it.
* Evidence from the consolidated core that manual sequencing costs measurable changeover
  time or due-date misses.
* Then: prototype **buy** against the same fixtures used by `CHAR-REALIZATION-TIME-01`, as
  an advisory sequencer proposing a Draft schedule the planner still approves — never as a
  system that writes an operative plan on its own.

## Consequences

* No solver dependency enters `pyproject.toml`; TC-W3-012 asserts it.
* Planner throughput on large lines depends on the schedule board's ergonomics, which is
  why URS-W3-020 budgets a 200-order board at ≤ 2 s.
* Sequence quality remains a human judgement, recorded in the schedule's decision reason
  and audit trail.
