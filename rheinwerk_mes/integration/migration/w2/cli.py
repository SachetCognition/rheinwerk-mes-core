"""Bench entrypoints for the W2 migration pilot (URS-W2-030…032).

Extends the W0-5 migration CLI *additively* — the published `run_all` signature is
untouched. The W2 pilot runs three independently-reversible load steps per plant and writes
a citable reconciliation report artefact::

    bench --site dev.localhost execute rheinwerk_mes.integration.migration.w2.cli.run_w2_migration
    bench --site dev.localhost execute rheinwerk_mes.integration.migration.w2.cli.rollback_step --args "['<run_id>']"
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import frappe

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.integration.migration.importer import JOURNAL_DIRECTORY
from rheinwerk_mes.integration.migration.w2 import extract as w2_extract
from rheinwerk_mes.integration.migration.w2 import loaders, reconcile
from rheinwerk_mes.integration.migration.w2 import rollback as w2_rollback
from rheinwerk_mes.integration.migration.w2.model import W2Extract

REPORT_FILENAME = "w2-pilot-reconciliation.md"

#: A migration run is a gated, audited act like any other quality-relevant transition
#: (URS-W2-034): the audit entry cites the run ids and the reconciliation verdict, and
#: references the report artefact so the entry is followable years later.
MIGRATION_GATE = "w2_migration_run"
MIGRATION_RULE = "URS-W2-030…032"

#: Reverse order used when a whole run is torn down: links → state → batches, so a produced
#: batch's links are gone before the batch itself is deleted.
TEARDOWN_ORDER = (loaders.STEP_LINKS, loaders.STEP_STATE, loaders.STEP_BATCHES)


def load_plant(extract: W2Extract) -> dict[str, str]:
	"""Run the three load steps for one plant; returns the per-step run ids."""
	batches = loaders.load_batches(extract)
	links = loaders.load_links(extract)
	state = loaders.load_state(extract)
	return {
		loaders.STEP_BATCHES: batches.run_id,
		loaders.STEP_LINKS: links.run_id,
		loaders.STEP_STATE: state.run_id,
	}


def rollback_plant(run_ids: dict[str, str]) -> dict[str, dict[str, int]]:
	"""Tear down one plant's run in dependency-safe order (links → state → batches)."""
	ordered = [run_ids[step] for step in TEARDOWN_ORDER if step in run_ids]
	return w2_rollback.rollback_runs(ordered)


def report_path() -> str:
	directory = frappe.get_site_path("private", "files", JOURNAL_DIRECTORY)
	os.makedirs(directory, exist_ok=True)
	return os.path.join(directory, REPORT_FILENAME)


def run_w2_migration(fixture_directory: str | None = None, keep_on_fail: bool = False) -> dict[str, Any]:
	"""Run the full W2 pilot for Plants A/B/C, reconcile and write the report artefact.

	On a reconciliation FAIL the run is rolled back by run id (per the URS rollback
	conditions) unless `keep_on_fail` is set for diagnosis. Returns a summary dict with the
	per-plant run ids, the report status and the artefact path.
	"""
	extracts = w2_extract.extract_all(fixture_directory)
	run_ids: dict[str, dict[str, str]] = {}
	for source, extract in extracts.items():
		run_ids[source] = load_plant(extract)
	frappe.db.commit()

	report = reconcile.build_report(extracts, run_ids)
	rolled_back = False
	if report.status == reconcile.FAIL and not keep_on_fail:
		for source in extracts:
			rollback_plant(run_ids[source])
		rolled_back = True

	path = report_path()
	Path(path).write_text(report.to_markdown(), encoding="utf-8")
	_audit_run(report, run_ids, rolled_back)

	summary = {
		"status": report.status,
		"rolled_back": rolled_back,
		"run_ids": run_ids,
		"report_path": path,
		"plants": {plant.source: plant.status for plant in report.plants},
	}
	print(f"W2 migration {report.status} — report at {path}")  # noqa: T201 (bench console)
	return summary


def _audit_run(report: Any, run_ids: dict[str, dict[str, str]], rolled_back: bool) -> str:
	"""Write the audit entry of one pilot run (URS-W2-034 / TC-W2-048)."""
	artefact = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": REPORT_FILENAME,
			"is_private": 1,
			"content": report.to_markdown(),
		}
	).insert(ignore_permissions=True)
	steps = ", ".join(
		f"{source}: {'/'.join(sorted(ids.values()))}" for source, ids in sorted(run_ids.items())
	)
	return audit.log_transition(
		gate=MIGRATION_GATE,
		rule=MIGRATION_RULE,
		document=artefact,
		from_state=None,
		to_state=report.status,
		detail=f"W2-Pilotmigration {report.status}"
		+ (" (zurückgerollt)" if rolled_back else "")
		+ f" — Läufe: {steps}",
	)


def rollback_step(run_id: str) -> dict[str, int]:
	"""Bench entry point: reverse a single W2 load step from its journal."""
	outcome = w2_rollback.rollback_run(run_id)
	frappe.db.commit()
	print(f"rollback {run_id}: {outcome}")  # noqa: T201 (bench console)
	return outcome


def render_report(fixture_directory: str | None = None) -> str:
	"""Return the reconciliation markdown for the current site state (no load/rollback)."""
	extracts = w2_extract.extract_all(fixture_directory)
	return reconcile.build_report(extracts).to_markdown()
