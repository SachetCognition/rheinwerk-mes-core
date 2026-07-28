# Wave W1 — Production Core

Plan/release and execute journeys end to end; execution gating hooks; recipe governance workflow; warehouse physical fidelity base.

**Exit:** planner + operator journeys pass acceptance; behaviour choices vs characterisation tests documented.

## Backlog

| # | Item | Disposition / golden source | Dossier finding (evidence) |
|---|---|---|---|
| W1-1 | Explicit production-order state machine layered over Work Order (pending/accepted/inProgress/completed/interrupted/abandoned/declined semantics) as Frappe workflow + hooks — never forking the anchor DocType | Absorb Qcadoo | ch. 3.1 `OrderState.java:31-81`; §7 implication 1 |
| W1-2 | Execution gating hooks: accept requires dates/line/technology; complete requires recorded output > 0; material-availability gate on release | Absorb Qcadoo | ch. 3.1 `OrderStateValidationService.java:44-63`; `OrderStatesListenerServicePFTD.java:580` |
| W1-3 | Keep/verify anchor hard stops: over-production errors, stopped-WO freeze, closed-terminal, expired-batch throw | Adopt ERPNext | ch. 3.2 §C rules table (`services/status.py:29-47`; `stock_ledger_entry.py:287-299`) |
| W1-4 | Recipe governance workflow on BOM/Routing: draft→checked→accepted→outdated with structural validators (tree completeness, unit match, in-use lock) | Absorb Qcadoo | ch. 3.1 `TechnologyState.java:33-66`, `TechnologyValidationService.java:91-707`; §7 implication 5 |
| W1-5 | Warehouse physical fidelity base: pallet/handling-unit + storage-location DocTypes; per-warehouse disposal algorithm (FIFO/LIFO/FEFO/LEFO) | Absorb Qcadoo | ch. 3.1 `ResourceFields.java:32-90`, `WarehouseAlgorithm.java:26-27`; §7 implication 4 |
| W1-6 | Draft-document stock reservations semantics reconciled with Stock Reservation Entry | Absorb Qcadoo + Adopt ERPNext | ch. 3.1 `ReservationsService.java:81-247`; ch. 3.2 `stock_reservation_entry.py:530-553`; §5.2 reservation row |
| W1-7 | Shop-floor operator journey on ERPNext Shop Floor/Job Cards incl. pause/resume and time logs | Adopt ERPNext | ch. 3.2 `job_card.py:1280-1397` |
| W1-8 | Role model: workflow-state-level permissions expressing Qcadoo's per-transition roles in Frappe RBAC | Absorb Qcadoo semantics | §7 implication 7; ch. 3.1 §B.2 (151 roles) |
| W1-9 | Expiry-enforcement policy decision (hard stop vs FEFO-advisory) recorded with business sign-off + characterisation deltas | Decision | §5.4 expired-stock divergence; §7 implication 6 |
| W1-10 | Characterisation-vs-behaviour choices documented per gate (parity or intentional divergence) | — | Wave exit criterion |
