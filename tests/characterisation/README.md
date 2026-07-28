# Characterisation harness — Qcadoo parity contracts

**Backlog:** W0-6 · **Requirement:** URS-W0-012 · **Test cases:** TC-W0-014, TC-W0-015

This harness is the programme's **regression floor**. Each contract encodes one piece of
legacy Qcadoo behaviour (read from `SachetCognition/Chem_mes@master`, semantics only —
never ported code), executes against committed fixture data, and fails loudly when the
behaviour drifts. The contracts run offline (no Frappe site) and gate every CI run.

## Layout

| Path | Purpose |
|---|---|
| `loader.py` | deterministic JSON fixture loader; German-first date parsing (DD.MM.YYYY) |
| `legacy_rules.py` | the legacy rules re-expressed in Python, each citing its Java source + line range |
| `api.py` | `Verdict`, the adapter resolution and the `ENTRYPOINTS` table (W1 handover) |
| `registry.py` | `Contract` dataclass + registry — contracts are enumerable by ID |
| `contracts/` | contract definitions (registration happens on import) |
| `fixtures/` | committed fixture documents, one per contract |
| `test_contracts.py` | pytest parametrisation over the registry (TC-W0-014) |
| `test_harness.py` | registry integrity + drift detection (TC-W0-015) |

Run them with:

```bash
pytest tests/characterisation          # offline, no site required
```

## Registered contracts

| Contract ID | Behaviour | Legacy baseline (`Chem_mes@master`) | URS / TC |
|---|---|---|---|
| `CHAR-ORDER-ACCEPT-01` | acceptance refused when dateFrom/dateTo/production line/technology missing | `OrderStateValidationService.java:44-47` | URS-W0-012 AC-1 / TC-W0-014 step 1 |
| `CHAR-ORDER-COMPLETE-01` | completion refused when doneQuantity = 0 | `OrderStateValidationService.java:54-63` | URS-W0-012 AC-2 / TC-W0-014 step 2 |
| `CHAR-FEFO-PICK-01` | FEFO picks earliest expiry first (BATCH-A-0002 before BATCH-A-0001), FIFO/LIFO/LEFO orders and the unknown-algorithm fallback | `ResourceManagementServiceImpl.java:1015-1027`, `WarehouseAlgorithm.java:26-27` | URS-W0-012 AC-3 / TC-W0-014 step 3 |
| `CHAR-TECH-VALIDATE-01` | technology structural validators: empty tree, unfilled input quantities, unit mismatches, technology used by an active order | `TechnologyValidationService.java:91-707` | URS-W0-012 / TC-W0-014 (fixtures encoded in W0, consumed by W1) |
| `CHAR-BATCH-STATE-01` | batch disposition machine: Released ⇄ Blocked reversible, reason mandatory, illegal edges refused; the Quarantined entry state asserted as **new behaviour** | `BatchState.java:31-44` | URS-W2-006 / TC-W2-038 |
| `CHAR-BLOCKED-PICK-01` | resources of a quality-blocked batch never reach a candidate list; the Quarantined exclusion asserted as **new behaviour** | `ResourceCriteriaModifiers.java:59,70` | URS-W2-010 / TC-W2-039 |
| `CHAR-EXPIRY-ISSUE-01` | expired resource issuable under Plant A's FEFO-advisory behaviour — **declared divergence** (W1 refuses it; see below) | `ResourceManagementServiceImpl.java:1015-1027` | URS-W1-030 / TC-W1-033 |
| `CHAR-SCHEDULE-STATE-01` | line-schedule machine: Draft → Approved / Rejected, every other edge refused; the legacy Approved → Rejected edge asserted as **new behaviour** (narrowed on purpose) | `ScheduleState.java:8-24` | URS-W3-005 / TC-W3-007 |
| `CHAR-REALIZATION-TIME-01` | realization time = TPZ + truncated(quantity × TJ × staff factor), 15 combinations incl. qty = 1 and TPZ = 0 | `OrderRealizationTimeServiceImpl.java:156-186` | URS-W3-006 / TC-W3-009 |

### New behaviour without a legacy counterpart

Where the estate adds a behaviour Plant A simply does not have — the `Quarantined` entry
state and its exclusion from picking (URS-W2-006/010) — or deliberately narrows one it does
have — the legacy `Approved → Rejected` schedule edge dropped by URS-W3-005 AC-3 — the
fixture case is flagged `new_behaviour` and carries **two** expectations: `expected` is the legacy verdict, pinned
while the contract runs against the fallback, and `expected_target` is the addition, asserted
as soon as the target entrypoint resolves. Unlike a `Divergence` this is not a conflict
between two readings of the same rule, so it needs no strict xfail and no business sign-off —
but it is measured rather than described in prose.

### Declared divergences

A contract may carry a `Divergence` (`registry.py`), which inverts the expectation for every
fixture case flagged `diverges`: the case is expected to **fail** against the target, and
`test_contracts.py` runs it as a strict xfail so the suite also fails if the divergence
quietly disappears. Only one W1 contract does this — `CHAR-EXPIRY-ISSUE-01`, whose decision
record (`docs/decisions/DEC-W1-030-expiry-policy.md`) carries the business sign-off that the
per-gate behaviour record (`python -m tools.behaviour.generate`) refuses to generate
without.

## Handover to W1 — implement these entrypoints

Every contract is evaluated through a thin adapter (`api.resolve`). While the target
function does not exist, the contract runs against the fixture-encoded legacy rule in
`legacy_rules.py`. **As soon as a W1 child adds the function below, the same contract and
the same fixtures start executing against production code** — no test change required,
and any behavioural difference fails CI immediately.

| Target entrypoint | Signature | Legacy fallback |
|---|---|---|
| `rheinwerk_mes.execution_gating.contracts.evaluate_order_acceptance` | `(order: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_order_acceptance` |
| `rheinwerk_mes.execution_gating.contracts.evaluate_order_completion` | `(order: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_order_completion` |
| `rheinwerk_mes.warehouse.contracts.picking_order` | `(resources: Sequence[Mapping[str, Any]], algorithm: str) -> Sequence[str]` | `legacy_rules.picking_order` |
| `rheinwerk_mes.manufacturing_core.contracts.evaluate_technology` | `(technology: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_technology` |
| `rheinwerk_mes.execution_gating.contracts.evaluate_expired_issue` | `(issue: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_expired_issue` |
| `rheinwerk_mes.genealogy.contracts.evaluate_batch_state_transition` | `(transition: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_batch_state_transition` |
| `rheinwerk_mes.genealogy.contracts.pickable_candidates` | `(resources: Sequence[Mapping[str, Any]]) -> Sequence[str]` | `legacy_rules.pickable_candidates` |
| `rheinwerk_mes.manufacturing_core.scheduling.contracts.evaluate_schedule_state_transition` | `(transition: Mapping[str, Any]) -> Verdict` | `legacy_rules.evaluate_schedule_state_transition` |
| `rheinwerk_mes.manufacturing_core.scheduling.contracts.realization_time` | `(inputs: Mapping[str, Any]) -> int` | `legacy_rules.realization_time` |

Contract details for the implementer:

* `Verdict` is `allowed: bool` + `errors: tuple[str, ...]`; the harness compares `errors`
  **in order** against the legacy message keys recorded in the fixtures. A W1
  implementation may translate those keys for the UI, but the entrypoint must return the
  keys so parity stays machine-checkable. If a deliberate deviation is agreed, record it
  in the wave's URS (as URS-W1-030 does for the expiry policy) and update the fixture in
  the same PR — never silently loosen an assertion.
* Input shapes are exactly the fixture payloads (`case["order"]`, `case["resources"]` +
  `case["algorithm"]`, `case["technology"]`). Keep the entrypoints pure functions over
  plain mappings so they stay runnable without a site; the DocType-facing hook should be a
  thin wrapper that builds the mapping from the document.
* Dates arrive German-first as `DD.MM.YYYY` strings (`loader.parse_de_date`); masses are kg.

## Adding a contract

1. Re-express the legacy rule in `legacy_rules.py` with a docstring citing the Java path
   and line range.
2. Add a fixture document under `fixtures/` (cases with `id`, `description`, inputs and
   the `expected` legacy verdict; the document cites its Java baseline).
3. Register a `Contract` in `contracts/` with its `concern` (entrypoint key), URS IDs and
   TC IDs, then document it in the tables above — `test_harness.py` enforces that.
