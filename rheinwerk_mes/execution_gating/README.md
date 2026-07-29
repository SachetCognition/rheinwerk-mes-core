# Execution Gating — Absorb (Wave W1)

Hard integrity gates re-implemented as Frappe hooks + an explicit 7-state order workflow layered over derived statuses:

- Material availability gate on order release
- Batch evidence + expiry enforcement on every tracking event
- Completion blocked until final recorded output exists

Landed so far:

| Module | Gate | Requirement | Legacy baseline |
|---|---|---|---|
| `order_state.py` | legal `exec_state` transition set (pure functions, no site needed) | URS-W1-002 | `OrderState.java:31-81` (`canChangeTo`) |
| `order_state_gating.py` | `Work Order.validate` doc_event refusing illegal transitions | URS-W1-002 | `StateChangeContextBuilderImpl.java:64`, `StateExecutorService.java:175,201` |
| `contracts.py` | parity entrypoints resolved by the characterisation harness | URS-W0-012 | fixtures under `tests/characterisation/fixtures/` |

Compliance-critical: dropping any gate is a regression for batch manufacturing (dossier implication #4).
Source lineage: Qcadoo `OrderStateValidationService`, `ProductionTrackingListenerService`, `OrderStatesListenerServicePFTD` (behavioural reference).
