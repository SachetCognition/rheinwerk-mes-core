"""Persistence of the reconciliation reports (URS-W0-011, EXIT-W0-2).

A round trip is only *demonstrable* if its report outlives the process that produced it.
Every run therefore archives its per-source report next to the run journal, under
`<site>/private/files/rheinwerk_mes_migration_reports/`, and `run_all` additionally writes
the three-source summary the wave-exit criterion is read from — one deterministic PASS/FAIL
for "master data from all three sources round-trips".

The summary lists the sources in `extractors.SOURCES` order with the run id each status
came from, so a reviewer can walk from the summary to the per-source report to the run
journal without consulting a shell history.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import frappe

from rheinwerk_mes.integration.migration.reconcile import FAIL, PASS, ReconciliationReport

REPORT_DIRECTORY = "rheinwerk_mes_migration_reports"

SUMMARY_FILENAME = "round-trip-summary.md"


def report_directory() -> str:
	directory = frappe.get_site_path("private", "files", REPORT_DIRECTORY)
	os.makedirs(directory, exist_ok=True)
	return directory


def report_path(run_id: str) -> str:
	return os.path.join(report_directory(), f"{run_id}.md")


def summary_path() -> str:
	return os.path.join(report_directory(), SUMMARY_FILENAME)


def write_report(report: ReconciliationReport) -> str:
	"""Archive one source's reconciliation report; returns the file path."""
	path = report_path(report.run_id)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(report.to_markdown())
	return path


def summary_status(reports: Sequence[ReconciliationReport]) -> str:
	"""PASS only when every source round-tripped — the W0 exit criterion (EXIT-W0-2)."""
	if not reports:
		return FAIL
	return FAIL if any(report.status == FAIL for report in reports) else PASS


def summary_markdown(reports: Sequence[ReconciliationReport]) -> str:
	lines = [
		"# Abstimmübersicht Stammdatenmigration — alle Quellen",
		"",
		f"- **Gesamtstatus:** {summary_status(reports)}",
		"",
		"| Quelle | Lauf | Positionen | Arbeitsplätze | Lager | Status | Bericht |",
		"|---|---|---|---|---|---|---|",
	]
	for report in reports:
		counts = {entity.entity: entity.source_count for entity in report.entities}
		lines.append(
			f"| {report.source} | {report.run_id} | {counts.get('item', 0)} | "
			f"{counts.get('work_centre', 0)} | {counts.get('warehouse', 0)} | {report.status} | "
			f"`{REPORT_DIRECTORY}/{report.run_id}.md` |"
		)
	return "\n".join(lines) + "\n"


def write_summary(reports: Sequence[ReconciliationReport]) -> str:
	"""Write the three-source summary read at wave exit; returns the file path."""
	path = summary_path()
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(summary_markdown(reports))
	return path
