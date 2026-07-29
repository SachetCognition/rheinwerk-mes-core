# Execution Gating — Absorb (Wave W1)

Hard integrity gates re-implemented as Frappe hooks + an explicit 7-state order workflow layered over derived statuses:

- Material availability gate on order release
- Batch evidence + expiry enforcement on every tracking event
- Completion blocked until final recorded output exists

Compliance-critical: dropping any gate is a regression for batch manufacturing (dossier implication #4).
Source lineage: Qcadoo `OrderStateValidationService`, `ProductionTrackingListenerService`, `OrderStatesListenerServicePFTD` (behavioural reference).

## Implemented gates

| Gate | Requirement | Transition | Legacy baseline (`Chem_mes@master`) |
|---|---|---|---|
| `gates.completion_gate` | URS-W1-007 | * → Completed | `OrderStateValidationService.java:54-63` |

`contracts.py` holds the parity rules as pure functions over plain mappings — no site
needed — and returns the legacy Qcadoo message keys. It carries the characterisation
handover entrypoints of `tests/characterisation/api.py`, so the W0 parity contracts
(`CHAR-ORDER-COMPLETE-01`) execute against this production code unchanged.

`gates.py` is the anchor-facing layer: it maps the `Work Order` document onto that mapping
(CDM-02), decides whether the save enters the gated state, and turns a refusal into the
German-first hard-gate modal naming rule, record and resolution. Gates judge only — they
never post or mutate fields — and are registered as `doc_events` in `hooks.py`, so the
anchor DocType stays unforked.
