# Wave plan — task list

Programme task list for the consolidation, populated from the *Production Systems Landscape — Reverse Engineering & Fit-Gap Dossier* (`docs/dossier/production-systems-dossier.md`). Each wave file carries its backlog with per-item disposition and dossier evidence.

| Wave | Theme | Status | Backlog |
|---|---|---|---|
| — | Reverse engineering & fit-gap dossier (programme input) | **Done** — dossier v1.0 committed (`docs/dossier/`) | — |
| [W0](W0-foundation.md) | Foundation: scaffold, canonical entities, migration tooling, characterisation harness | Next up | 8 items (W0-1…W0-8) |
| [W1](W1-production-core.md) | Production core: order state machine, gating, recipe governance, warehouse fidelity base | Pending W0 exit | 10 items (W1-1…W1-10) |
| [W2](W2-traceability-quality.md) | Traceability & quality: genealogy, blocking, QI, CoA, ISA-88, hazmat | Pending W1 exit | 10 items (W2-1…W2-10) |
| [W3](W3-planning-boundary.md) | Planning & boundary: MRP, finite capacity, ERP interface, SCADA/OPC-UA | Pending W2 exit | 7 items (W3-1…W3-7) |
| [W4](W4-cutover-decommission.md) | Cutover & decommission: per-plant cutover, backfill, legacy archival | Pending W3 exit | 7 items (W4-1…W4-7) |

Cross-wave rules (from the dossier's consolidation implications, §7):

1. Absorbed Qcadoo behaviour is always a re-implementation validated by characterisation tests — never a code port (implication 1).
2. Anchor DocTypes are never forked; absorbed semantics land as hooks/workflows/custom DocTypes (ARCHITECTURE.md layering).
3. Open questions in dossier §8.2 (plant settings, genealogy completeness, lot coverage at Plant B, external syncs) must be answered before the wave that depends on them exits.
