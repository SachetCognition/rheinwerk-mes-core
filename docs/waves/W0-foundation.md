# Wave W0 — Foundation

Platform scaffold; canonical entities (item, work centre, BOM/recipe, production order); master-data migration tooling; CI + characterisation harness.

**Exit:** canonical entities live; master data from all three sources round-trips; regression floor executing.

## Backlog

Source: *Production Systems Landscape — Reverse Engineering & Fit-Gap Dossier* (`docs/dossier/production-systems-dossier.md`); citations refer to chapter evidence indices at the pinned commits.

| # | Item | Disposition / golden source | Dossier finding (evidence) |
|---|---|---|---|
| W0-1 | Scaffold Frappe app `rheinwerk_mes` with module skeletons and CI (lint + test runner) | Adopt (ERPNext substrate) | ERPNext is the healthiest platform: CI workflows, 515 test files (ch. 3.2 §D) |
| W0-2 | Canonical Item/Product master + UoM conversions, with field mapping from Qcadoo `product` model, ERPNext `Item`, OFBiz `Product` | Adopt ERPNext master data | Master data Rich in all three; semantic map in dossier §5.2 |
| W0-3 | Canonical Work Centre entity (map: Qcadoo workstation/productionLine, ERPNext Workstation, OFBiz FixedAsset machine group) | Adopt ERPNext Workstation | §5.2 work-centre row — OFBiz models machines as accounting assets |
| W0-4 | Canonical BOM/recipe & production-order entities (anchor DocTypes, no forks) | Adopt ERPNext BOM/Work Order | §6.2 recipe/BOM golden source = ERPNext |
| W0-5 | Master-data migration tooling: extractors for Qcadoo PostgreSQL schema, ERPNext DocTypes, OFBiz entity XML/derby exports; round-trip fixtures for all three | — | §7 implication 4 (data-model migration, not copy) |
| W0-6 | Characterisation-test harness: encode Qcadoo order gating (`OrderStateValidationService`), technology validators, FEFO picking order as executable parity contracts | Absorb (Qcadoo semantics) | ch. 3.1 §C.3 rules table; ADR-001 consequence |
| W0-7 | Evidence-pack generator: wave-exit report linking backlog items → dossier findings → code/tests | — | `docs/evidence/README.md` audit spine |
| W0-8 | Decide + record naming/numbering scheme (Qcadoo DB-trigger sequences vs ERPNext naming series) | Adopt ERPNext naming series | ch. 3.1 §C.3 (trigger-generated numbers) vs ch. 3.2 (naming series) |
