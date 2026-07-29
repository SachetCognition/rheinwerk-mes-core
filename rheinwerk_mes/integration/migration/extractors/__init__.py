"""Per-source master-data extractors.

Every extractor is a pure function `extract(path) -> CanonicalExtract`: it reads a legacy
export and produces the canonical import format. No extractor talks to a Frappe site, so
extraction and its determinism contract are testable offline.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

from .ofbiz import DEFAULT_FIXTURE as OFBIZ_FIXTURE
from .ofbiz import extract as extract_ofbiz

EXTRACTORS: dict[str, Callable[[Path], CanonicalExtract]] = {"ofbiz": extract_ofbiz}

DEFAULT_FIXTURES: dict[str, str] = {"ofbiz": OFBIZ_FIXTURE}

SOURCES: tuple[str, ...] = tuple(EXTRACTORS)


def extract(source: str, path: str | Path) -> CanonicalExtract:
	"""Run the extractor for `source` over the legacy export at `path`."""
	if source not in EXTRACTORS:
		raise ValueError(f"unknown migration source {source!r}; expected one of {', '.join(SOURCES)}")
	return EXTRACTORS[source](Path(path))


__all__ = ["DEFAULT_FIXTURES", "EXTRACTORS", "SOURCES", "extract", "extract_ofbiz"]
