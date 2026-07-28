"""Per-source master-data extractors (URS-W0-008, URS-W0-009, URS-W0-010).

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
from .ofbiz import DEFAULT_FIXTURE as OFBIZ_FIXTURE
from .ofbiz import extract as extract_ofbiz
from .qcadoo import DEFAULT_FIXTURE as QCADOO_FIXTURE
from .qcadoo import extract as extract_qcadoo

EXTRACTORS: dict[str, Callable[[Path], CanonicalExtract]] = {
	"qcadoo": extract_qcadoo,
	"ofbiz": extract_ofbiz,
	"erpnext": extract_erpnext,
}

DEFAULT_FIXTURES: dict[str, str] = {
	"qcadoo": QCADOO_FIXTURE,
	"ofbiz": OFBIZ_FIXTURE,
	"erpnext": ERPNEXT_FIXTURE,
}

SOURCES: tuple[str, ...] = ("qcadoo", "ofbiz", "erpnext")


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
	"extract_ofbiz",
	"extract_qcadoo",
]
