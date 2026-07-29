"""Offline entry point that writes canonical import files (URS-W0-018 AC-2).

    python -m rheinwerk_mes.integration.migration.extract --source qcadoo \\
        --output build/plant-a.canonical.json
    python -m rheinwerk_mes.integration.migration.extract --all --output-directory build

Extraction never touches a Frappe site, so the canonical import file is reproducible from
the committed fixture in CI. The file is the artefact the determinism contract is stated
over: repeated runs over unchanged fixtures produce byte-identical bytes, which
`--verify-determinism` asserts in-process by extracting twice and comparing digests.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from rheinwerk_mes.integration.migration import extractors
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

REPO_ROOT = Path(__file__).resolve().parents[3]

#: `<source>.canonical.json` — the file name the CI determinism job compares across runs.
FILE_SUFFIX = ".canonical.json"


def default_fixture(source: str) -> Path:
	return REPO_ROOT / extractors.DEFAULT_FIXTURES[source]


def extract_source(source: str, fixture: str | Path | None = None) -> CanonicalExtract:
	"""Extract one source's committed fixture (or `fixture`) into the canonical format."""
	return extractors.extract(source, Path(fixture) if fixture else default_fixture(source))


def digest(extract: CanonicalExtract) -> str:
	"""SHA-256 of the canonical import file bytes this extract serialises to."""
	return hashlib.sha256(extract.to_json().encode("utf-8")).hexdigest()


def write_extract(source: str, output: str | Path, fixture: str | Path | None = None) -> CanonicalExtract:
	"""Extract `source` and write the canonical import file to `output`."""
	extract = extract_source(source, fixture)
	destination = Path(output)
	destination.parent.mkdir(parents=True, exist_ok=True)
	destination.write_text(extract.to_json(), encoding="utf-8")
	return extract


def output_path(source: str, directory: str | Path) -> Path:
	return Path(directory) / f"{source}{FILE_SUFFIX}"


def verify_determinism(source: str, fixture: str | Path | None = None) -> str:
	"""Extract `source` twice and return the digest; raises when the runs differ."""
	first = extract_source(source, fixture).to_json()
	second = extract_source(source, fixture).to_json()
	if first != second:
		raise AssertionError(f"{source}: repeated extraction is not byte-identical (URS-W0-018 AC-2)")
	return hashlib.sha256(first.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--source", choices=extractors.SOURCES, help="single source to extract")
	parser.add_argument("--all", action="store_true", help="extract every source")
	parser.add_argument("--fixture", help="source export to read (default: the committed fixture)")
	parser.add_argument("--output", help="canonical import file to write (single source only)")
	parser.add_argument("--output-directory", help=f"directory to write `<source>{FILE_SUFFIX}` into")
	parser.add_argument(
		"--verify-determinism",
		action="store_true",
		help="extract each source twice and fail unless both runs are byte-identical",
	)
	arguments = parser.parse_args(argv)

	if bool(arguments.source) == bool(arguments.all):
		parser.error("give exactly one of --source or --all")
	if arguments.all and arguments.output:
		parser.error("--all writes one file per source; use --output-directory")
	if arguments.all and arguments.fixture:
		parser.error("--fixture applies to a single --source")
	if not (arguments.output or arguments.output_directory or arguments.verify_determinism):
		parser.error("nothing to do: give --output, --output-directory or --verify-determinism")

	sources = extractors.SOURCES if arguments.all else (arguments.source,)
	for source in sources:
		if arguments.verify_determinism:
			print(f"{source}: deterministic, sha256={verify_determinism(source, arguments.fixture)}")
		destination = arguments.output or (
			output_path(source, arguments.output_directory) if arguments.output_directory else None
		)
		if destination is None:
			continue
		extract = write_extract(source, destination, arguments.fixture)
		counts = ", ".join(f"{entity}={count}" for entity, count in extract.counts().items())
		print(f"{source}: {destination} ({counts}) sha256={digest(extract)}")
		for exception in extract.exceptions:
			print(
				f"exception {exception.entity} {exception.source_identifier}: {exception.reason}",
				file=sys.stderr,
			)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
