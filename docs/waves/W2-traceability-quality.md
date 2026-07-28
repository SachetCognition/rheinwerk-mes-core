# Wave W2 — Traceability & Quality

Genealogy object model; batch blocking; QI adoption; CoA rebuild; ISA-88 recipes; hazmat master data.

**Exit:** full multi-level trace demonstrable; CoA generated from inspection results; recipe scaling functional.

## Backlog

| # | Item | Disposition / golden source | Dossier finding (evidence) |
|---|---|---|---|
| W2-1 | Genealogy object model as system-of-record: Batch DocType extensions + Tracking Record (produced batch ↔ used batches) with forward/backward tree browsing | Absorb Qcadoo | ch. 3.1 `TrackingRecordFields.java:31-49`, `AdvancedGenealogyTreeViewListeners.java:71-73` |
| W2-2 | Unified batch object: identity + QA state (released/quarantined/blocked) + expiry + genealogy links — collapsing Qcadoo's dual model and ERPNext's stateless Batch | Absorb + extend | §7 implication 2; ch. 3.1 §B.4; ch. 3.2 `batch.py:97-115` |
| W2-3 | Batch blocking/quarantine with propagation through genealogy trees and exclusion from picking | Absorb + extend | ch. 3.1 `BatchState.java:31-44`, `ResourceCriteriaModifiers.java:59,70`; §7 implication 3 |
| W2-4 | Adopt Quality Inspection engine (typed inspections, parametric readings, templates) and wire QI gates to the W1 state machine | Adopt ERPNext | ch. 3.2 `quality_inspection.py:265-336`, `quality_inspection_service.py:21-127` |
| W2-5 | Certificates of Analysis: generate CoA from inspection results per batch (white space — net-new) | Rebuild | §6.3 (absent in all three) |
| W2-6 | ISA-88 batch recipes: unit procedures/phases + recipe scaling over BOM/Routing (white space — net-new) | Rebuild | §6.3; ch. G ratings (Absent in all three) |
| W2-7 | Hazmat/regulatory master data (UN numbers, SDS references, storage classes) on Item/Batch (white space — net-new; completes in W3) | Rebuild | §6.3 |
| W2-8 | Warehouse fidelity completion: quarantine locations, pallet balances, stocktaking/repacking journeys | Absorb Qcadoo | ch. 3.1 `storageLocation.xml:37-54`, `RepackingState.java`, `StocktakingState.java` |
| W2-9 | Multi-level trace demo: acceptance test proving full forward + backward trace incl. blocked-batch propagation | — | Wave exit criterion |
| W2-10 | E-signature decision for compliance-critical transitions (no legacy precedent — white space) | Decision / Rebuild | §6.3; audit findings ch. §E of all three |
| W2-11 | Pilot migration of open batches, genealogy history and legacy quality flags into the canonical Batch, incl. reconciliation report and rehearsed rollback | Migrate (Qcadoo + OFBiz) | ch. 3.1 `TrackingRecordFields.java`, `BatchState.java:31-44`; OFBiz `WorkEffortInventoryAssign`/`Produced` (`lotId` absence = trace boundary) |
