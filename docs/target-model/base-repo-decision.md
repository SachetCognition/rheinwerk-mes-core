# Base Repository Decision (Stage 2.2)

**Decision: `SachetCognition/Chem_erpnext` (ERPNext) is the base for the consolidated application built in `SachetCognition/rheinwerk-mes-core`.** Qcadoo MES (`Chem_mes`) is a semantics donor only; OFBiz (`VM_ofbiz-framework`) is retired (data-migration source only).

## Decision form

| | |
|---|---|
| Status | Accepted (confirms ADR-001 with Stage 1 evidence) |
| Options considered | Base on Chem_erpnext · base on Chem_mes · base on VM_ofbiz-framework · greenfield |
| Scoring | ADR-001 weights: functional 35 / data model 20 / technical health 20 / extensibility 15 / UX 10 |

## Weighted comparison (from dossier Parts 3–6)

| Criterion (weight) | ERPNext | Qcadoo MES | OFBiz |
|---|---|---|---|
| Functional depth (35%) | 14 Rich / 7 Adequate of 30 capabilities; only real quality engine, planning/MRP, valuation | 11 Rich, deepest in execution/traceability/warehouse | 5 Rich; wins no capability area |
| Data-model fitness (20%) | DocType metadata + immutable SLE/GLE ledgers; extensible without schema forks | Rich but Java-bound; dual batch model; single schema | Generic entity engine; optional lots break traceability |
| Technical health (20%) | Python 3 / active CI / 515 test files / current framework | Java 8, Spring-XML, snapshot deps from third-party Nexus (unreproducible builds) | Java 17 but manufacturing module functionally frozen |
| Extensibility (15%) | hooks/doc-events/custom apps designed for absorption without forking | AOP/plugin model, but extension = more Java 8 estate | Component model, weak for this team's stack |
| UX (10%) | Modern desk + shop-floor pages | jqGrid/JSP-era | Declarative screens, dated |

**Weighted outcome: ERPNext wins every criterion except raw execution-semantics depth — and that depth is carried over as re-implemented rules (Absorb), which is exactly what the anchor's extension model is designed for.**

## Rationale (summary)

1. **Breadth + health:** the anchor must be the system that is broadest and healthiest, because everything else is grafted onto it. That is ERPNext by a wide margin (dossier §6.2 platform-substrate row).
2. **Depth is portable, platforms are not:** Qcadoo's winning behaviours are enum/listener *rules* — re-implementable as Frappe workflows/hooks with characterisation-test parity. Making Qcadoo the base would mean building quality, planning, valuation, multi-plant and a modern UI *into* an ageing Java 8 platform with unreproducible builds (implication 10).
3. **OFBiz eliminated:** wins no capability area; manufacturing is Adequate-at-best, quality Absent, lots optional (dossier §6.2 "Anything from OFBiz: none").
4. **Greenfield eliminated:** discards a working quality engine, planning stack, ledgers and RBAC that score Rich, for no compensating gain.
5. **Consequence for repo layout:** `rheinwerk-mes-core` hosts a custom Frappe app (`rheinwerk_mes`) installed alongside the ERPNext base; anchor DocTypes are never forked (ARCHITECTURE.md layering); Qcadoo/OFBiz code is never vendored in.

## What "base" does NOT mean

- Not a fork of `Chem_erpnext`: the base is consumed as an upstream dependency; all Rheinwerk behaviour lives in the `rheinwerk_mes` app in this repo.
- Not carrying ERPNext's finance/buying/selling as books of record — those remain group-ERP territory (ADR-002); modules stay installed only as far as stock/GL integrity requires.
