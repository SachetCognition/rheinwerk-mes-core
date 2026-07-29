"""Per-source master-data extractors (URS-W0-009).

Every extractor is a pure function `extract(path) -> CanonicalExtract`: it reads a
committed fixture export and produces the canonical import format. No extractor talks
to a Frappe site, so extraction (and its determinism contract, URS-W0-018) is testable
offline.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

from .erpnext_legacy import DEFAULT_FIXTURE as ERPNEXT_FIXTURE
from .erpnext_legacy import extract as extract_erpnext

EXTRACTORS: dict[str, Callable[[Path], CanonicalExtract]] = {
	"erpnext": extract_erpnext,
}

DEFAULT_FIXTURES: dict[str, str] = {
	"erpnext": ERPNEXT_FIXTURE,
}

SOURCES: tuple[str, ...] = ("erpnext",)


def extract(source: str, path: str | Path) -> CanonicalExtract:
	"""Run the extractor for `source` over the fixture export at `path`."""
	if source not in EXTRACTORS:
		raise ValueError(f"unknown migration source {source!r}; expected one of {', '.join(SOURCES)}")
	return EXTRACTORS[source](Path(path))


__all__ = [
	"DEFAULT_FIXTURES",
	"EXTRACTORS",
	"SOURCES",
	"extract",
	"extract_erpnext",
]
