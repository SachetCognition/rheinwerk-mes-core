# Capability Disposition Map (Stage 2.2)

Single-page map: **sub-capability → source disposition → target home**. Golden-source calls from the dossier (Part 6.2) were re-confirmed against the validated evidence; two calls are refined (marked ⚠). Dispositions: **Adopt** (use anchor as shipped) / **Absorb** (re-implement source semantics on anchor) / **Rebuild** (net-new) / **Retire**.

| Sub-capability | Golden source (dossier) | Confirmed? | Disposition | Target home | Wave |
|---|---|---|---|---|---|
| Order state machine & transitions | Qcadoo | Confirmed | Absorb | Integrity | W1 |
| Execution gating (release/complete gates) | Qcadoo | Confirmed | Absorb | Integrity | W1 |
| Posting hard stops (over-production, expired batch) | ERPNext | Confirmed | Adopt | Anchor | W1 |
| Shop-floor UI / job cards / time logs | ERPNext | Confirmed | Adopt | Anchor | W1 |
| BOM & routing definition | ERPNext | Confirmed | Adopt | Anchor | W0 |
| Recipe approval governance | Qcadoo | Confirmed | Absorb | Integrity | W1 |
| ISA-88 master/control recipes, scaling | — (white space) | n/a | Rebuild | Chemicals | W2 |
| Batch master data | Qcadoo ⚠ | **Refined**: unified canonical entity beyond both (CDM-01); ERPNext Batch is the storage anchor, Qcadoo contributes state semantics | Absorb + extend | Integrity | W2 |
| Batch genealogy | Qcadoo | Confirmed | Absorb | Integrity | W2 |
| Quarantine / blocking with propagation | Qcadoo | Confirmed (extension needed) | Absorb + extend | Integrity | W2 |
| Quality inspection engine | ERPNext | Confirmed | Adopt | Anchor | W2 |
| Parametric QC specs | ERPNext | Confirmed | Adopt | Anchor | W2 |
| Certificates of Analysis | — (white space) | n/a | Rebuild | Chemicals | W2 |
| E-signatures | — (white space) | n/a | Rebuild | Chemicals | W2/W3 (Q2) |
| Warehouse tree & putaway | ERPNext | Confirmed | Adopt | Anchor | W0 |
| Pallets / handling units / storage locations | Qcadoo | Confirmed | Absorb | Integrity | W1 |
| FEFO/FIFO/LIFO disposal algorithms | Qcadoo ⚠ | **Refined**: anchor already ships FIFO/LIFO/Expiry picking; absorb only the per-warehouse algorithm selection + LEFO | Adopt + absorb delta | Anchor + Integrity | W1 |
| Draft-document reservations | Qcadoo | Confirmed | Absorb | Integrity | W1 |
| Order/batch-level stock reservation | ERPNext | Confirmed | Adopt | Anchor | W1 |
| Valuation methods & repost engine | ERPNext | Confirmed | Adopt | Anchor (postings → Boundary) | W3 |
| Production Plan / MPS / MRP | ERPNext | Confirmed | Adopt | Anchor | W3 |
| Finite-capacity norms & line schedules | Qcadoo (partial) | Confirmed | Absorb (optimiser: buy, Q3) | Integrity | W3 |
| Item/UoM master data | ERPNext | Confirmed | Adopt | Anchor | W0 |
| Hazmat/regulatory data | — (white space) | n/a | Rebuild | Chemicals | W2/W3 |
| SCADA / OPC-UA adapter | — (white space) | n/a | Rebuild | Chemicals | W3 |
| Group-ERP interface (orders/confirmations/GL) | — (boundary) | n/a | Rebuild | Boundary | W3 |
| Reporting & dashboards | ERPNext | Confirmed | Adopt | Anchor | W1–W3 |
| CMMS / maintenance events | Qcadoo | Confirmed (scope Q6) | Absorb | Integrity | W3 |
| Audit trail / versioning | ERPNext | Confirmed | Adopt | Anchor | W0 |
| Multi-plant / RBAC / i18n | ERPNext | Confirmed | Adopt (+ workflow-state permissions) | Anchor + Integrity | W0/W1 |
| Finance, buying, selling apps | n/a | n/a | Retire → group ERP | — | W4 |
| OFBiz (all manufacturing behaviour) | none | Confirmed | Retire (data-migration source) | — | W4 |
