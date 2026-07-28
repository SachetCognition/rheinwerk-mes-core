# Evidence packs

One evidence pack per wave, auto-generated at wave exit: every shipped item traced back through
disposition record → register entry → dossier finding, with source file-path citations.
This directory is the audit spine of the consolidation.

## Generating a pack (W0-7, URS-W0-013)

```bash
python -m tools.evidence.generate --wave W0             # writes W0-evidence-pack.md
python -m tools.evidence.generate --wave W0 --html      # also renders docs/html/W0-evidence-pack.html
python -m tools.evidence.generate --wave W0 --strict    # wave-exit gate: fail on open evidence
python -m tools.evidence.generate --wave W0 --check     # fail if the committed pack is stale
```

The generator reads the committed specs only — the backlog table in `docs/waves/W{n}-*.md`
(item + dossier citation), the requirements in `docs/urs/URS-W{n}-*.md`, the traceability
matrix in `docs/test/TST-W{n}-*.md` — plus the TC IDs cited in `tests/**` docstrings and the
`manual-evidence.md` register. Nothing is maintained twice, so the pack cannot drift from the
specs.

Statuses: **complete**, **evidence-incomplete** (linked but a mapped test case has no
evidence yet — always reported, never omitted) and **unlinked** (no URS→TC chain; makes the
generator exit non-zero). Packs are regenerated, never hand-edited.
