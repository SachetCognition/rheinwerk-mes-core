"""Wave-exit evidence-pack generator (W0-7, URS-W0-013).

`python -m tools.evidence.generate --wave W0` links every backlog item of a wave to its
dossier citation, its URS IDs, its mapped test-case IDs and the tests that implement them,
and writes `docs/evidence/W{n}-evidence-pack.md`.
"""

from __future__ import annotations

__all__ = ["model", "parsers", "render"]
