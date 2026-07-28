"""Bench-invocable entry points for the master-data migration (W0-5).

    bench --site dev.localhost execute \\
        rheinwerk_mes.integration.migration.cli.run_round_trip --kwargs "{'source': 'qcadoo'}"
    bench --site dev.localhost execute rheinwerk_mes.integration.migration.cli.run_all
    bench --site dev.localhost execute \\
        rheinwerk_mes.integration.migration.cli.rollback --kwargs "{'run_id': 'qcadoo-2026…'}"

`run_round_trip` extracts the committed fixture for `source`, imports it, re-exports the
target and reconciles the two, printing the German-first markdown report. A FAIL report
rolls the run back automatically unless `keep_on_fail=True`, so a failed migration never
leaves partial master data behind (URS-W0-011 AC-3).

Fixture location defaults to `tests/fixtures/legacy/**` in the app checkout and can be
overridden per run with `fixture=<path>`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import frappe

from rheinwerk_mes.integration.migration import extractors
from rheinwerk_mes.integration.migration.canonical import CanonicalExtract
from rheinwerk_mes.integration.migration.exporter import reexport
from rheinwerk_mes.integration.migration.importer import import_extract, new_run_id
from rheinwerk_mes.integration.migration.reconcile import FAIL, ReconciliationReport, reconcile
from rheinwerk_mes.integration.migration.rollback import rollback_result, rollback_run


def app_root() -> Path:
	"""Repository root of the installed app (holds `tests/fixtures/legacy`)."""
	return Path(frappe.get_app_path("rheinwerk_mes")).resolve().parent


def fixture_path(source: str, fixture: str | Path | None = None) -> Path:
	if fixture:
		return Path(fixture).resolve()
	return app_root() / extractors.DEFAULT_FIXTURES[source]


def extract_source(source: str, fixture: str | Path | None = None) -> CanonicalExtract:
	"""Extract one source's committed fixture into the canonical import format."""
	return extractors.extract(source, fixture_path(source, fixture))


def round_trip(
	source: str,
	*,
	fixture: str | Path | None = None,
	keep_on_fail: bool = False,
) -> ReconciliationReport:
	"""Extract → import → re-export → reconcile one source; roll back on FAIL."""
	started = time.monotonic()
	extract = extract_source(source, fixture)
	run_id = new_run_id(source)
	result = import_extract(extract, run_id=run_id)
	report = reconcile(
		extract,
		reexport(extract),
		run_id=run_id,
		imported=result.imported,
		deferred=result.deferred,
		duration_seconds=time.monotonic() - started,
	)
	if report.status == FAIL and not keep_on_fail:
		rollback_result(result)
	return report


def run_round_trip(source: str = "qcadoo", fixture: str | None = None, keep_on_fail: Any = False) -> dict:
	"""Bench entry point: run and print one source's round-trip reconciliation."""
	report = round_trip(source, fixture=fixture, keep_on_fail=bool(keep_on_fail))
	print(report.to_markdown())
	frappe.db.commit()
	return {"source": source, "run_id": report.run_id, "status": report.status}


def run_all(fixture_directory: str | None = None) -> dict:
	"""Bench entry point: run the round trip for all three sources."""
	summary = {}
	for source in extractors.SOURCES:
		fixture = (
			str(Path(fixture_directory) / Path(extractors.DEFAULT_FIXTURES[source]).name)
			if fixture_directory
			else None
		)
		summary[source] = run_round_trip(source, fixture=fixture)
	return summary


def rollback(run_id: str) -> dict:
	"""Bench entry point: reverse a previous run from its journal."""
	outcome = rollback_run(run_id)
	frappe.db.commit()
	print(f"rollback {run_id}: {outcome}")
	return outcome
