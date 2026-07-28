"""W2 migration of open batches, genealogy history and legacy quality flags.

URS-W2-030…032 (`docs/urs/URS-W2-traceability-quality.md` §3.10). This package *extends*
the W0-5 three-source migration framework in the parent package
(`rheinwerk_mes.integration.migration`): it reuses the reversible run journal
(`importer.JournalEntry` / `write_journal` / `read_journal`), the deterministic
spot-check sampler (`canonical.spot_check_sample`) and the German-first report style, and
adds the batch-level loaders and reconcilers the master-data round trip did not cover.

Read `docs/design/W2-migration.md` for the load-step / rollback / retention design and
`docs/design/W2-genealogy.md` for the canonical `Batch`, `qa_state` and genealogy-link
APIs this package writes through.
"""

from __future__ import annotations
