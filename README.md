# Rheinwerk MES Core

**Company:** Rheinwerk Chemie GmbH (fictitious) — a centralised European speciality-chemicals manufacturer.
**Repository purpose:** target repository for the consolidated Manufacturing Execution System, replacing three legacy production systems identified in the estate rationalisation programme:

| Legacy system | Role in estate | Disposition |
|---|---|---|
| Qcadoo MES (`Chem_mes`) | Plant A homegrown MES | Absorb — genealogy, gating, recipe governance semantics carried into this repo |
| ERPNext (`Chem_erpnext`) | Plant C ERP (manufacturing/quality/stock scope) | Adopt — anchor substrate for this repo |
| Apache OFBiz (`VM_ofbiz-framework`) | Plant B legacy ERP | Retire — reference material only, no code carried |

## Target shape

A single Frappe application ("one-app" outcome of the rationalisation gate) composed of:

- **Adopted core (~60%)** — ERPNext manufacturing, stock and quality DocTypes as the base.
- **Absorbed capability (~25%)** — Qcadoo batch-genealogy object model, hard execution gates, explicit order state machine, recipe lifecycle governance, warehouse physical fidelity (quarantine, pallets, FEFO).
- **Net-new chemicals capability (~15%)** — ISA-88 batch recipes, Certificates of Analysis, regulatory/hazmat data, SCADA/OPC-UA connectivity.

ERP-boundary capabilities (finance, buying, selling) are **not** in scope: this MES exposes an order-in / confirmation-out and GL-posting interface to the group ERP (see `docs/adr/ADR-002-erp-boundary.md`).

## Repository status

🚧 **Placeholder / scaffold.** Structure, dispositions and wave plan are committed; implementation lands wave by wave (see `docs/waves/`). Every module README states its disposition, source lineage and wave assignment — the traceability spine of the programme:

> dossier finding → register entry → disposition record → wave backlog item → code/test → evidence pack

## Layout

```
rheinwerk_mes/            Frappe app package (modules below)
  manufacturing_core/     Adopt   — W1/W3
  genealogy/              Absorb  — W2
  execution_gating/       Absorb  — W1
  quality/                Adopt + Rebuild (CoA) — W2
  warehouse/              Absorb  — W1/W2
  recipe_isa88/           Rebuild — W2
  regulatory_hazmat/      Rebuild — W2/W3
  integration/            Rebuild — W3 (ERP interface, SCADA/OPC-UA adapter)
docs/adr/                 Architecture decision records
docs/waves/               Forward-engineering wave plans (W0–W4)
docs/evidence/            Evidence packs and source-lineage index
tests/                    Characterisation + acceptance suites
```
