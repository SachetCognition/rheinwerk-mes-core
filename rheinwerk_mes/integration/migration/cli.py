"""Bench-invocable entry points for the master-data migration (W0-5).

    bench --site dev.localhost execute \\
        rheinwerk_mes.integration.migration.cli.run_extract --kwargs "{'source': 'ofbiz'}"
    bench --site dev.localhost execute \\
        rheinwerk_mes.integration.migration.cli.run_import --kwargs "{'source': 'ofbiz'}"

Both write the canonical extract and its exceptions report to
`<site>/private/files/rheinwerk_mes_migration/`; `run_import` additionally lands the
extract on the anchor DocTypes. The export defaults to the committed fixture for the
source and can be pointed at a real export with `fixture=<path>`.
"""

from __future__ import annotations

import os
from pathlib import Path

import frappe

from rheinwerk_mes.integration.migration import exceptions_report, extractors
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract
from rheinwerk_mes.integration.migration.importer import import_extract

OUTPUT_DIRECTORY = "rheinwerk_mes_migration"


def app_root() -> Path:
	"""Repository root of the installed app (holds `tests/fixtures/legacy`)."""
	return Path(frappe.get_app_path("rheinwerk_mes")).resolve().parent


def fixture_path(source: str, fixture: str | Path | None = None) -> Path:
	if fixture:
		return Path(fixture).resolve()
	return app_root() / extractors.DEFAULT_FIXTURES[source]


def output_directory() -> Path:
	directory = Path(frappe.get_site_path("private", "files", OUTPUT_DIRECTORY))
	os.makedirs(directory, exist_ok=True)
	return directory


def extract_source(source: str, fixture: str | Path | None = None) -> CanonicalExtract:
	"""Extract one source's export into the canonical import format."""
	return extractors.extract(source, fixture_path(source, fixture))


def write_outputs(extract: CanonicalExtract) -> dict[str, str]:
	"""Write the canonical extract and its exceptions report; return the paths."""
	directory = output_directory()
	extract_file = directory / f"{extract.source}-extract.json"
	report_file = directory / f"{extract.source}-exceptions.md"
	extract_file.write_text(extract.to_json(), encoding="utf-8")
	report_file.write_text(exceptions_report.to_markdown(extract), encoding="utf-8")
	return {"extract": str(extract_file), "exceptions_report": str(report_file)}


def run_extract(source: str = "ofbiz", fixture: str | None = None) -> dict:
	"""Bench entry point: extract one source and write extract plus exceptions report."""
	extract = extract_source(source, fixture)
	paths = write_outputs(extract)
	print(exceptions_report.to_markdown(extract))
	return {"source": source, "counts": extract.counts(), "exceptions": len(extract.exceptions), **paths}


def run_import(source: str = "ofbiz", fixture: str | None = None) -> dict:
	"""Bench entry point: extract one source and import it onto the anchor DocTypes."""
	extract = extract_source(source, fixture)
	paths = write_outputs(extract)
	result = import_extract(extract)
	frappe.db.commit()
	print(exceptions_report.to_markdown(extract))
	return {
		"source": source,
		"imported": result.imported,
		"exceptions": len(extract.exceptions),
		**paths,
	}
