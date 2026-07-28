# Execution Gating — Absorb (Wave W1)

Hard integrity gates re-implemented as Frappe hooks + an explicit 7-state order workflow layered over derived statuses:

- Material availability gate on order release
- Batch evidence + expiry enforcement on every tracking event
- Completion blocked until final recorded output exists

Compliance-critical: dropping any gate is a regression for batch manufacturing (dossier implication #4).
Source lineage: Qcadoo `OrderStateValidationService`, `ProductionTrackingListenerService`, `OrderStatesListenerServicePFTD` (behavioural reference).
