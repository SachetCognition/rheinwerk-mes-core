"""Command-line entry point that writes a canonical import file (URS-W0-008 AC-1).

    python -m rheinwerk_mes.integration.migration.extract --source qcadoo \\
        --output build/plant-a.canonical.json

Extraction never touches a Frappe site or a live plant, so the canonical import file
is reproducible from the committed fixture in CI. Repeated runs over unchanged input
are byte-identical (URS-W0-018).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rheinwerk_mes.integration.migration import extractors
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_fixture(source: str) -> Path:
	return REPO_ROOT / extractors.DEFAULT_FIXTURES[source]


def write_extract(source: str, output: str | Path, fixture: str | Path | None = None) -> CanonicalExtract:
	"""Extract `source` and write the canonical import file to `output`."""
	extract = extractors.extract(source, Path(fixture) if fixture else default_fixture(source))
	destination = Path(output)
	destination.parent.mkdir(parents=True, exist_ok=True)
	destination.write_text(extract.to_json(), encoding="utf-8")
	return extract


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--source", choices=extractors.SOURCES, default="qcadoo")
	parser.add_argument("--fixture", help="source export to read (default: the committed fixture)")
	parser.add_argument("--output", required=True, help="canonical import file to write")
	arguments = parser.parse_args(argv)

	extract = write_extract(arguments.source, arguments.output, arguments.fixture)
	counts = ", ".join(f"{entity}={count}" for entity, count in extract.counts().items())
	print(f"{arguments.source}: {arguments.output} ({counts})")
	for exception in extract.exceptions:
		print(
			f"exception {exception.entity} {exception.source_identifier}: {exception.reason}", file=sys.stderr
		)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
