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

🚧 **Requirements complete, pre-implementation.** Stages 1–5 of the programme are committed: the reverse-engineering dossier, target capability model, canonical data model with ADRs, HLD/LLD, the wave-based implementation plan, and the per-wave User Requirements Specifications and Test & Verification documents. Implementation lands wave by wave (see `docs/waves/`). Every module README states its disposition, source lineage and wave assignment — the traceability spine of the programme:

> dossier finding → register entry → disposition record → wave backlog item → URS requirement → acceptance criteria → test case → code/test → evidence pack

### Delivery tracking (Jira)

The wave requirements are mirrored on the Jira board **Sach_Sales_MES** (project key **SSM**), labelled `rheinwerk-mes`:

| Wave | Jira issue | Requirements | Test cases |
|---|---|---|---|
| W0 — Foundation | SSM-2 | 18 (`docs/urs/URS-W0-foundation.md`) | 21 (`docs/test/TST-W0-foundation.md`) |
| W1 — Production Core | SSM-3 | 35 (`docs/urs/URS-W1-production-core.md`) | 39 (`docs/test/TST-W1-production-core.md`) |
| W2 — Traceability & Quality | SSM-4 | 36 (`docs/urs/URS-W2-traceability-quality.md`) | 50 (`docs/test/TST-W2-traceability-quality.md`) |
| W3 — Planning & Boundary | SSM-5 | 23 (`docs/urs/URS-W3-planning-boundary.md`) | 27 (`docs/test/TST-W3-planning-boundary.md`) |
| W4 — Cutover & Decommission | SSM-6 | 14 (`docs/urs/URS-W4-cutover-decommission.md`) | 18 (`docs/test/TST-W4-cutover-decommission.md`) |

Each wave is a wave-level Jira issue (type *Workstream* — the project scheme's Epic level) with one child *Task* per URS requirement carrying the requirement statement, lineage and acceptance criteria verbatim. The URS documents are the record copy; Jira is the working copy. Test cases live only in the TST documents and are referenced from the Jira issues, and the TST wave acceptance checklist is what closes each wave issue.

## Programme artefacts

| Stage | Artefact | Location |
|---|---|---|
| 1 | Reverse Engineering & Fit-Gap Dossier (per-app dossiers, 30-capability model, cross-app comparison, golden sources, white space) | `docs/dossier/` (md + docx) |
| 1 | Wave task lists (W0–W4 backlogs, 42 items) | `docs/waves/` |
| 2.1 | Target capability model (T1–T30; white-space, retire-only and ERP-boundary marks) | `docs/target-model/target-capability-model.md` |
| 2.2 | Capability disposition map (sub-capability → disposition → target home → wave) | `docs/target-model/capability-disposition-map.md` |
| 2.2 | Base repository decision (ERPNext base; Qcadoo semantics donor; OFBiz retired) | `docs/target-model/base-repo-decision.md` (+ docx) |
| 2.3 | Canonical data model CDM-01…08 with field-level source mappings | `docs/canonical-model/` |
| 2.3 | Canonical-entity ADRs (sign-off gates before the waves that touch them) | `docs/adr/ADR-003…010` |
| 3 | High-Level Design / Low-Level Design | `docs/design/HLD.md`, `docs/design/LLD.md` |
| 4 | Consolidation implementation project plan (waves, milestones M0–M4, RAID) | `docs/plan/` (md + xlsx) |
| — | Target technology landscape (pinned versions + rationale for 40+ plant scale) | `docs/design/target-technology-landscape.md` |
| 5 | Wave User Requirements Specifications URS-W0…W4 (126 requirements, full lineage) | `docs/urs/` |
| 5 | Wave Test & Verification documents TST-W0…W4 (155 test cases, traceability matrices, wave acceptance checklists) | `docs/test/` |
| — | Standalone styled HTML for all artefacts (start at `index.html`) | `docs/html/` (regenerate via `tools/htmlgen/`) |

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
docs/adr/                 Architecture decision records (ADR-001…010)
docs/dossier/             Stage 1 reverse-engineering & fit-gap dossier
docs/target-model/        Stage 2 target capability model, disposition map, base-repo decision
docs/canonical-model/     Stage 2 canonical data model (CDM-01…08)
docs/design/              Stage 3 HLD and LLD
docs/plan/                Stage 4 implementation project plan (md + xlsx)
docs/urs/                 Stage 5 wave User Requirements Specifications (URS-W0…W4)
docs/test/                Stage 5 wave Test & Verification documents (TST-W0…W4)
docs/html/                Standalone styled HTML for all artefacts
docs/waves/               Forward-engineering wave plans (W0–W4)
docs/evidence/            Evidence packs and source-lineage index
tools/htmlgen/            HTML artefact generator (pandoc + mermaid-cli)
tests/                    Characterisation + acceptance suites
.github/workflows/        CI pipeline (lint + test runner)
```

## Continuous integration

Every pull request runs `.github/workflows/ci.yml` — a **lint** job (`ruff check` plus
`ruff format --check`) and a **test** job (`pytest tests`). Either job failing makes the
pipeline red, so the W0 regression floor (URS-W0-002, verified by TC-W0-003) gates merges
from the first commit.

The toolchain is pinned in `requirements-dev.txt` and its configuration lives in
`pyproject.toml`, so the pipeline reproduces locally:

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest tests -rs
```

Site-backed suites (Frappe site with the ERPNext substrate on MariaDB/Redis) skip when no
site is reachable; the stack job that provides one lands with the substrate scaffold
(URS-W0-001).
