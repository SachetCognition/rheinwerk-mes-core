"""Deterministic fixture loader for the characterisation harness (URS-W0-012).

Fixtures are committed JSON documents under `fixtures/`. They are the *legacy* truth:
each case records the input rows exactly as Qcadoo would hold them plus the verdict the
Qcadoo code produces for those rows. Dates are written German-first (DD.MM.YYYY) per
`rheinwerk-mes-design-SKILL.md`; the loader parses them into `datetime.date` so ordering
comparisons are unambiguous.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

DE_DATE_FORMAT = "DD.MM.YYYY"


def parse_de_date(value: str) -> date:
	"""Parse a German-format date (DD.MM.YYYY) into a `date`."""
	day, month, year = (int(part) for part in value.split("."))
	return date(year, month, day)


def format_de_date(value: date) -> str:
	"""Render a `date` German-first (DD.MM.YYYY)."""
	return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


@cache
def _read(name: str) -> str:
	path = FIXTURE_DIR / name
	if not path.exists():
		raise FileNotFoundError(f"characterisation fixture not found: {path}")
	return path.read_text(encoding="utf-8")


def load_fixture(name: str) -> dict[str, Any]:
	"""Load a fixture document by file name (e.g. `order_gating.json`)."""
	document = json.loads(_read(name))
	if not isinstance(document, dict):
		raise TypeError(f"fixture {name} must contain a JSON object at the top level")
	return document


def load_cases(name: str) -> list[dict[str, Any]]:
	"""Load a fixture's `cases` list, sorted by case id for deterministic ordering."""
	document = load_fixture(name)
	cases = document.get("cases")
	if not isinstance(cases, list) or not cases:
		raise ValueError(f"fixture {name} declares no cases")
	for case in cases:
		if "id" not in case:
			raise ValueError(f"fixture {name} has a case without an id")
	return sorted(cases, key=lambda case: str(case["id"]))
