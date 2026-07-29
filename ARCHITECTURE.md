# Architecture (target state)

**Stack:** Frappe framework (Python, MariaDB/PostgreSQL, Redis workers), metadata-driven DocTypes, hook-based extension. Chosen by disposition math — the anchor hosting the largest share of Adopt/Absorb capability weight — recorded in `docs/adr/ADR-001-target-stack.md`.

## Layering

1. **Anchor layer** — ERPNext manufacturing/stock/quality DocTypes (BOM, Routing, Work Order, Job Card, Stock Entry, Batch/SABB, Quality Inspection, Workstation, Production Plan).
2. **Integrity layer (absorbed)** — genealogy object model, hard state-machine gating, recipe approval workflow, quarantine/FEFO warehouse semantics. Implemented as Frappe hooks, workflows and custom DocTypes — never as forks of anchor DocTypes.
3. **Chemicals layer (new build)** — ISA-88 recipe structures, CoA generation over QI readings, hazmat/regulatory master data, SCADA/OPC-UA adapter.
4. **Boundary layer** — group-ERP interface (orders in, confirmations out, GL postings out). No finance, buying or selling logic lives in this repo.

## Non-negotiable behaviours (compliance-critical, carried from legacy)

- Batch evidence and expiry enforcement on every production tracking event.
- Material-availability gate on order release; completion blocked without final recorded output.
- Batch blocking/quarantine propagates through genealogy trees.
- Full forward and backward trace as a system-of-record object model, not a derived report.
- Every create/update/delete of canonical master data (Item, Workstation, BOM, Work Order) is audited with user, timestamp and old→new field values on the platform version log, retrievable per record via `rheinwerk_mes.manufacturing_core.audit.get_audit_trail` (URS-W0-015).
