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

ERP-boundary capabilities (finance, buying, selling) are **not** in scope: this MES exposes an order-in / confirmation-out and GL-posting interface to the group ERP (see `docs/30-architecture/adr/ADR-002-erp-boundary.md`).

## Repository status

🚧 **Requirements complete, pre-implementation.** Stages 1–5 of the programme are committed: the reverse-engineering dossier, target capability model, canonical data model with ADRs, HLD/LLD, the wave-based implementation plan, and the per-wave User Requirements Specifications and Test & Verification documents. Implementation lands wave by wave (see `docs/40-planning/`). Every module README states its disposition, source lineage and wave assignment — the traceability spine of the programme:

> dossier finding → register entry → disposition record → wave backlog item → URS requirement → acceptance criteria → test case → code/test → evidence pack

### Delivery tracking (Jira)

The wave requirements are mirrored on the Jira board **Sach_Sales_MES** (project key **SSM**), labelled `rheinwerk-mes`:

| Wave | Jira issue | Requirements | Test cases |
|---|---|---|---|
| W0 — Foundation | SSM-2 | 18 (`docs/20-requirements/foundation/URS-W0-foundation.md`) | 21 (`docs/50-verification/foundation/TST-W0-foundation.md`) |
| W1 — Production Core | SSM-3 | 35 (`docs/20-requirements/production-core/URS-W1-production-core.md`) | 39 (`docs/50-verification/production-core/TST-W1-production-core.md`) |
| W2 — Traceability & Quality | SSM-4 | 36 (`docs/20-requirements/traceability-quality/URS-W2-traceability-quality.md`) | 50 (`docs/50-verification/traceability-quality/TST-W2-traceability-quality.md`) |
| W3 — Planning & Boundary | SSM-5 | 23 (`docs/20-requirements/planning-boundary/URS-W3-planning-boundary.md`) | 27 (`docs/50-verification/planning-boundary/TST-W3-planning-boundary.md`) |
| W4 — Cutover & Decommission | SSM-6 | 14 (`docs/20-requirements/cutover-decommission/URS-W4-cutover-decommission.md`) | 18 (`docs/50-verification/cutover-decommission/TST-W4-cutover-decommission.md`) |

Each wave is a wave-level Jira issue (type *Workstream* — the project scheme's Epic level) with one child *Task* per URS requirement carrying the requirement statement, lineage and acceptance criteria verbatim. The URS documents are the record copy; Jira is the working copy. Test cases live only in the TST documents and are referenced from the Jira issues, and the TST wave acceptance checklist is what closes each wave issue.

## Programme artefacts

| Stage | Artefact | Location |
|---|---|---|
| 1 | Reverse Engineering & Fit-Gap Dossier (per-app dossiers, 30-capability model, cross-app comparison, golden sources, white space) | `docs/10-discovery/dossier/` (md + docx) |
| 1 | Wave task lists (W0–W4 backlogs, 42 items) | `docs/40-planning/` |
| 2.1 | Target capability model (T1–T30; white-space, retire-only and ERP-boundary marks) | `docs/30-architecture/target-model/target-capability-model.md` |
| 2.2 | Capability disposition map (sub-capability → disposition → target home → wave) | `docs/30-architecture/target-model/capability-disposition-map.md` |
| 2.2 | Base repository decision (ERPNext base; Qcadoo semantics donor; OFBiz retired) | `docs/30-architecture/target-model/base-repo-decision.md` (+ docx) |
| 2.3 | Canonical data model CDM-01…08 with field-level source mappings | `docs/30-architecture/canonical-model/` |
| 2.3 | Canonical-entity ADRs (sign-off gates before the waves that touch them) | `docs/30-architecture/adr/ADR-003…010` |
| 3 | High-Level Design / Low-Level Design | `docs/30-architecture/design/HLD.md`, `docs/30-architecture/design/LLD.md` |
| 4 | Consolidation implementation project plan (waves, milestones M0–M4, RAID) | `docs/40-planning/` (md + xlsx) |
| — | Target technology landscape (pinned versions + rationale for 40+ plant scale) | `docs/30-architecture/design/target-technology-landscape.md` |
| 5 | Wave User Requirements Specifications URS-W0…W4 (126 requirements, full lineage) | `docs/20-requirements/` |
| 5 | Wave Test & Verification documents TST-W0…W4 (155 test cases, traceability matrices, wave acceptance checklists) | `docs/50-verification/` |
| — | Standalone styled HTML for all artefacts (start at `index.html`) | `docs/90-rendered/` (regenerate via `tools/htmlgen/`) |

## Layout

The repository is organised on two axes: **SDLC phase** (numbered `docs/` folders) and **business domain** (subfolders within each phase, and the Frappe modules in code).

```
rheinwerk_mes/                Frappe app package — modules by business domain
  manufacturing_core/         Adopt   — W1/W3 (planning, scheduling, shop floor)
  genealogy/                  Absorb  — W2 (batch lineage, blocking)
  execution_gating/           Absorb  — W1 (order state machine, hard gates)
  quality/                    Adopt + Rebuild (CoA) — W2
  warehouse/                  Absorb  — W1/W2 (pallets, FEFO, quarantine)
  recipe_isa88/               Rebuild — W2 (ISA-88 batch recipes)
  regulatory_hazmat/          Rebuild — W2/W3
  integration/                Rebuild — W3 (ERP interface, SCADA/OPC-UA adapter)
docs/
  10-discovery/               Stage 1 — reverse-engineering & fit-gap dossier
  20-requirements/            Stage 5 — URS per business domain
    foundation/  production-core/  traceability-quality/  planning-boundary/  cutover-decommission/
  30-architecture/            Stages 2–3 — ARCHITECTURE.md, ADRs, canonical + target model, HLD/LLD
  40-planning/                Stage 4 — project plan, CONSOLIDATION.md, wave backlogs per domain
  50-verification/            Stage 5 — TST documents per domain + evidence packs
  90-rendered/                Standalone styled HTML for all artefacts
.agents/skills/rheinwerk-mes-design/   UI design-system skill
tools/htmlgen/                HTML artefact generator (pandoc + mermaid-cli)
tests/                        Characterisation + acceptance suites
```

Domain folders map to delivery waves: `foundation` (W0), `production-core` (W1), `traceability-quality` (W2), `planning-boundary` (W3), `cutover-decommission` (W4).
