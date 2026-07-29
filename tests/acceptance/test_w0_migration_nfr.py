"""Migration-tooling performance and determinism (URS-W0-018), offline.

TC-W0-021 step 1 (AC-1) — the round-trip budget gate: an overrun fails the summary even
when the data reconciles. The measured site-backed timing lives in
`test_w0_migration_round_trip.py`; here the gate itself is proven.
TC-W0-021 step 2 (AC-2) — the canonical import *file* is byte-identical across repeated
extractor runs, including runs in separate processes with a different hash seed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from rheinwerk_mes.integration.migration import extract, extractors  # noqa: E402
from rheinwerk_mes.integration.migration.nfr import (  # noqa: E402
	ROUND_TRIP_BUDGET_SECONDS,
	BudgetCheck,
	budget_markdown,
	budget_status,
	check_budget,
)
from rheinwerk_mes.integration.migration.reconcile import (  # noqa: E402
	EntityReconciliation,
	ReconciliationReport,
)


def report(source: str, duration_seconds: float) -> ReconciliationReport:
	"""A PASS reconciliation report that took `duration_seconds`."""
	return ReconciliationReport(
		source=source,
		run_id=f"{source}-20260101-000000",
		entities=(
			EntityReconciliation(
				entity="item",
				source_count=1,
				imported_count=1,
				reexported_count=1,
				source_checksum="a" * 64,
				reexported_checksum="a" * 64,
				sample=("RW-CHM-0001",),
				differences=(),
			),
		),
		duration_seconds=duration_seconds,
	)


def run_extractor(output_directory: Path, hash_seed: str) -> None:
	"""Write every source's canonical import file from a fresh interpreter."""
	environment = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(REPO_ROOT)}
	subprocess.run(
		[
			sys.executable,
			"-m",
			"rheinwerk_mes.integration.migration.extract",
			"--all",
			"--output-directory",
			str(output_directory),
		],
		cwd=REPO_ROOT,
		env=environment,
		check=True,
		capture_output=True,
	)


def test_tc_w0_021_repeated_extraction_writes_byte_identical_files(tmp_path):
	"""TC-W0-021 step 2 (URS-W0-018 AC-2): two extractor runs over unchanged fixtures, in
	separate processes with different hash seeds, write byte-identical canonical files."""
	first, second = tmp_path / "first", tmp_path / "second"
	run_extractor(first, "0")
	run_extractor(second, "12345")

	for source in extractors.SOURCES:
		left = extract.output_path(source, first)
		right = extract.output_path(source, second)
		assert left.read_bytes() == right.read_bytes(), f"{source}: canonical file is not deterministic"
		assert left.read_text(encoding="utf-8") == extract.extract_source(source).to_json()


def test_tc_w0_021_verify_determinism_reports_a_stable_digest():
	"""TC-W0-021 step 2 (URS-W0-018 AC-2): the determinism check CI runs returns the same
	digest as the written file, so a drift is visible as a changed hash."""
	for source in extractors.SOURCES:
		assert extract.verify_determinism(source) == extract.digest(extract.extract_source(source))


def test_tc_w0_021_budget_gate_fails_a_run_that_overruns():
	"""TC-W0-021 step 1 (URS-W0-018 AC-1): the 30-minute per-source budget is enforced on
	the report's own duration — a PASS reconciliation that overruns is still a FAIL."""
	inside = report("qcadoo", ROUND_TRIP_BUDGET_SECONDS - 60)
	overrun = report("ofbiz", ROUND_TRIP_BUDGET_SECONDS + 1)

	assert check_budget(inside) == BudgetCheck("qcadoo", inside.run_id, inside.duration_seconds)
	assert check_budget(inside).status == "PASS"
	assert check_budget(inside).headroom_seconds == 60
	assert check_budget(overrun).status == "FAIL"
	assert overrun.status == "PASS"

	assert budget_status([inside]) == "PASS"
	assert budget_status([inside, overrun]) == "FAIL"
	assert budget_status([]) == "FAIL"


def test_tc_w0_021_budget_table_names_every_source_and_its_headroom():
	"""TC-W0-021 step 1 (URS-W0-018 AC-1): the summary's budget table carries the measured
	duration per source, so the CI artefact is the evidence for the 30-minute criterion."""
	table = budget_markdown([report("qcadoo", 12.5), report("erpnext", 8.0)])
	assert "30 min je Quelle" in table
	assert "| qcadoo | 12.5 | 1800 |" in table
	assert "| erpnext | 8.0 | 1800 |" in table
