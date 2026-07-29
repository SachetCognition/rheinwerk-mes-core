"""Migration-tooling non-functional gates: wall-clock budget and determinism (URS-W0-018).

Two contracts hold over the tooling itself rather than over the migrated data:

* **AC-1** — a source's full round trip (extract → import → re-export → reconcile) finishes
  inside `ROUND_TRIP_BUDGET_SECONDS` on the CI runner. The budget is checked on the same
  `duration_seconds` the reconciliation report already carries, so the archived report is
  the evidence and no separate timing log has to be trusted.
* **AC-2** — repeated extraction over unchanged fixtures yields byte-identical canonical
  import files (`extract.verify_determinism`, enforced offline in CI).

A run that reconciles PASS but overruns the budget is *not* a healthy run: `budget_status`
reports it as FAIL, which propagates into the round-trip summary the wave-exit criterion
is read from.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rheinwerk_mes.integration.migration.reconcile import FAIL, PASS, ReconciliationReport

#: URS-W0-018 AC-1 — per-source round-trip wall-clock budget on the CI runner.
ROUND_TRIP_BUDGET_SECONDS: float = 30 * 60


@dataclass(frozen=True)
class BudgetCheck:
	"""One source's wall-clock measurement against the round-trip budget."""

	source: str
	run_id: str
	duration_seconds: float
	budget_seconds: float = ROUND_TRIP_BUDGET_SECONDS

	@property
	def status(self) -> str:
		return PASS if self.duration_seconds <= self.budget_seconds else FAIL

	@property
	def headroom_seconds(self) -> float:
		"""Seconds left in the budget; negative when the run overran it."""
		return self.budget_seconds - self.duration_seconds

	def __str__(self) -> str:
		return f"{self.source}: {self.duration_seconds:.1f} s of {self.budget_seconds:.0f} s ({self.status})"


def check_budget(
	report: ReconciliationReport, budget_seconds: float = ROUND_TRIP_BUDGET_SECONDS
) -> BudgetCheck:
	"""Measure one round-trip report against the budget (AC-1)."""
	return BudgetCheck(
		source=report.source,
		run_id=report.run_id,
		duration_seconds=report.duration_seconds,
		budget_seconds=budget_seconds,
	)


def budget_status(reports: Sequence[ReconciliationReport]) -> str:
	"""PASS only when every source stayed inside its budget."""
	if not reports:
		return FAIL
	return FAIL if any(check_budget(report).status == FAIL for report in reports) else PASS


def budget_markdown(reports: Sequence[ReconciliationReport]) -> str:
	"""German-first budget table for the round-trip summary."""
	lines = [
		f"## Laufzeitbudget (URS-W0-018 AC-1: {ROUND_TRIP_BUDGET_SECONDS / 60:.0f} min je Quelle)",
		"",
		"| Quelle | Dauer (s) | Budget (s) | Reserve (s) | Status |",
		"|---|---|---|---|---|",
	]
	for report in reports:
		check = check_budget(report)
		lines.append(
			f"| {check.source} | {check.duration_seconds:.1f} | {check.budget_seconds:.0f} | "
			f"{check.headroom_seconds:.1f} | {check.status} |"
		)
	return "\n".join(lines) + "\n"
