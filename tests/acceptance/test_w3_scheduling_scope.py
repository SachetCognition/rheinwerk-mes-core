"""TC-W3-012 — Won't-scope audit: no optimiser component, D4 decision record with a status.

Verifies **URS-W3-009** (the recorded exclusion of a constraint-based optimiser and the D4
build-vs-buy decision record) through **TC-W3-012** of
`docs/test/TST-W3-planning-boundary.md`. Offline: the audit reads committed artefacts.
"""

from __future__ import annotations

import re

DECISION_RECORD = "docs/decisions/DEC-W3-009-optimiser-build-vs-buy.md"
DESIGN_NOTE = "docs/design/W3-finite-capacity.md"
DECISION_REGISTER = "docs/plan/consolidation-project-plan.md"

#: Names a constraint solver or an optimisation component would carry.
OPTIMISER_MARKERS = ("ortools", "pulp", "cvxpy", "mip.model", "constraint_solver", "cp_model")


def test_no_optimiser_component_is_delivered(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 step 1 — the scheduling package holds no solver."""
	sources = list((repo_root / "rheinwerk_mes").rglob("*.py"))
	assert sources
	for path in sources:
		text = path.read_text("utf-8").lower()
		for marker in OPTIMISER_MARKERS:
			assert marker not in text, f"{path} references the optimiser library {marker}"


def test_no_solver_dependency_is_declared(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 step 1 — no solver enters the dependency set."""
	manifest = (repo_root / "pyproject.toml").read_text("utf-8").lower()
	for marker in OPTIMISER_MARKERS:
		assert marker not in manifest


def test_scheduling_sequence_is_the_planners(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 step 1 — sequencing keeps the given order, it does not optimise."""
	sequencing = (repo_root / "rheinwerk_mes/manufacturing_core/scheduling/sequencing.py").read_text("utf-8")
	assert "URS-W3-009" in sequencing
	assert "sorted(" not in sequencing, "the sequence must be the planner's, not a computed optimum"


def test_d4_decision_record_carries_a_status(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 step 2 — D4 exists, with a status and a sign-off."""
	record = (repo_root / DECISION_RECORD).read_text("utf-8")
	status = re.search(r"^- \*\*Status:\*\*\s*(\S.+)$", record, re.MULTILINE)
	assert status, "the D4 record carries no status line"
	assert status.group(1).strip()
	assert re.search(r"^- \*\*Sign-off:\*\*\s*\S", record, re.MULTILINE)
	assert "URS-W3-009" in record and "TC-W3-012" in record
	assert "build" in record.lower() and "buy" in record.lower()


def test_d4_record_is_linked_to_the_programme_register(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 step 2 — the record answers register dependency D4."""
	register = (repo_root / DECISION_REGISTER).read_text("utf-8")
	assert re.search(r"\|\s*D4\s*\|.*build vs buy", register, re.IGNORECASE)
	record = (repo_root / DECISION_RECORD).read_text("utf-8")
	assert DECISION_REGISTER in record


def test_exclusion_is_documented_in_the_design_note(repo_root):
	"""URS-W3-009 AC-1 / TC-W3-012 — the design note states the exclusion and points at D4."""
	design = (repo_root / DESIGN_NOTE).read_text("utf-8")
	assert "URS-W3-009" in design
	assert DECISION_RECORD in design
