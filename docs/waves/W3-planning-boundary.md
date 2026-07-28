# Wave W3 — Planning & Boundary

Production Plan/MRP + finite capacity; group-ERP interface; SCADA/OPC-UA adapter.

**Exit:** planning journey complete; ERP interface contract tested with fixtures.

## Backlog

| # | Item | Disposition / golden source | Dossier finding (evidence) |
|---|---|---|---|
| W3-1 | Production Plan/MRP journey (sales input → explosion → material requests → orders) on anchor | Adopt ERPNext | ch. 3.2 `production_plan/services/material_request.py:141`, MPS/forecast doctypes |
| W3-2 | Finite-capacity layer: line schedules, changeover norms, TJ/TPZ-style realization times over anchor slot search | Absorb Qcadoo (partial) | ch. 3.1 `ScheduleState.java:8-24`, `OrderRealizationTimeServiceImpl.java`; §6.2 (no optimiser anywhere) |
| W3-3 | Group-ERP interface: orders in, confirmations out, GL postings out; contract fixtures + tests | Rebuild (boundary) | ADR-002; ch. 3.2 costing/GL evidence (`stock_controller.py`) |
| W3-4 | Costing/valuation at the boundary: perpetual-inventory GL postings mapped to group ERP accounts | Adopt ERPNext (boundary) | ch. 3.2 `item.json:387-390`, `stock_ledger.py:1726-1729` |
| W3-5 | SCADA/OPC-UA adapter (white space — net-new): tracking events from process control into production records | Rebuild | §6.3 (absent in all three) |
| W3-6 | Hazmat/regulatory completion: shipping/ADR data at the boundary, label data | Rebuild | §6.3 |
| W3-7 | Survey + contract-freeze of existing external syncs (Qcadoo `externalNumber/externalSynchronized` consumers, ERPNext integrations) | — | ch. 3.1 `OrderFields.java:48,88`; open question 6 (§8.2) |
| W3-8 | Wave NFR evidence (planning/board and scan performance, audit completeness, German-first i18n, permission matrix) and the e-signature enforcement W2 deferred here | — | Wave exit criterion; `docs/decisions/DEC-W2-029-e-signature-policy.md` |
