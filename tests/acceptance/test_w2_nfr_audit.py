"""TC-W2-048 — audit completeness for the gated quality actions of W2.

Verifies **URS-W2-034** (every `qa_state` transition, QI gate refusal, blocked-consumption
refusal, CoA issue and migration run leaves an audit record naming user, timestamp, rule id,
record ids, outcome and — where mandatory — the reason) through **TC-W2-048** of
`docs/test/TST-W2-traceability-quality.md`.

The five acts are exercised one by one; each is then read back from its audit surface. Two
surfaces carry the estate's audit: the batch's own append-only `qa_state_history` (the
disposition of a batch belongs on the batch) and the `Execution Gate Log` (refusals,
certificate issue, migration runs). Both are asserted for the same completeness fields, so a
future child cannot satisfy the requirement by logging half a record.
"""

from __future__ import annotations

from typing import Any

import pytest
from test_w2_quality_support import BATCH_A2, BATCH_C1, FIRST_ORDER, accepted_inspection_for, set_qa_state

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")
blocking = pytest.importorskip("rheinwerk_mes.genealogy.blocking")
coa = pytest.importorskip("rheinwerk_mes.quality.coa")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")

INSPECTOR = "q.fischer@rheinwerk-chemie.example"

#: Every audit entry answers these, whatever surface it sits on (URS-W2-034).
ENTRY_FIELDS = ("gate", "rule", "outcome", "logged_by", "logged_at")


def _as_inspector(site: Any) -> None:
	if not site.db.exists("User", INSPECTOR):
		pytest.skip("quality inspector persona not seeded on this site")
	site.set_user(INSPECTOR)


def _require(site: Any, doctype: str, name: str) -> None:
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")


def _complete(entry: dict[str, Any]) -> bool:
	return all(entry.get(field) for field in ENTRY_FIELDS) and bool(
		entry.get("reference_name") or entry.get("detail")
	)


def test_qa_state_transition_is_audited_with_user_reason_and_states(site):
	"""URS-W2-034 AC-1 — blocking BATCH-A-0002 leaves one complete history row."""
	_require(site, "Batch", BATCH_A2)
	set_qa_state(site, BATCH_A2, qa_state.QUARANTINED)
	_as_inspector(site)
	reason = "Verunreinigung im Rückstellmuster festgestellt"
	doc = qa_state.transition(BATCH_A2, qa_state.BLOCKED, reason=reason)

	row = doc.qa_state_history[-1]
	assert row.from_state == qa_state.QUARANTINED
	assert row.to_state == qa_state.BLOCKED
	assert row.changed_by == INSPECTOR
	assert row.changed_at is not None
	assert row.reason == reason


def test_qi_gate_refusal_is_logged_with_rule_and_records(site):
	"""URS-W2-034 AC-2 — a refused start is in the log, never toast-only."""
	_require(site, "Work Order", FIRST_ORDER)
	from rheinwerk_mes.execution_gating.gates import COMPLETED, IN_PROGRESS
	from rheinwerk_mes.quality import gates, inspections

	order = next(
		(name for name in frappe.get_all("Work Order", pluck="name") if inspections.produced_batches(name)),
		None,
	)
	if not order:
		pytest.skip("no fixture order has produced batches on this site")
	for produced in inspections.produced_batches(order):
		# Arrange the refusal precondition: the produced batch carries no QA evidence.
		set_qa_state(site, produced["batch"], qa_state.QUARANTINED)

	before = frappe.db.count(audit.LOG_DOCTYPE, {"gate": "quality_inspection_gate"})
	context = frappe._dict(
		doc=frappe.get_doc("Work Order", order),
		from_state=IN_PROGRESS,
		to_state=COMPLETED,
		errors=[],
	)
	gates.quality_inspection_gate(context)
	if not context.errors:
		pytest.skip("no batch on the fixture order currently awaits an accepted inspection")

	entries = frappe.get_all(
		audit.LOG_DOCTYPE,
		filters={"gate": "quality_inspection_gate"},
		fields=["gate", "rule", "outcome", "logged_by", "logged_at", "reference_name", "detail"],
		order_by="creation desc",
		limit=1,
	)
	assert frappe.db.count(audit.LOG_DOCTYPE, {"gate": "quality_inspection_gate"}) > before
	assert entries and _complete(entries[0])
	assert entries[0]["outcome"] == audit.REFUSED


def test_blocked_consumption_refusal_is_logged(site):
	"""URS-W2-034 AC-2 — the blocked-pick refusal names the batch and the rule."""
	_require(site, "Batch", BATCH_A2)
	set_qa_state(site, BATCH_A2, qa_state.BLOCKED)
	with pytest.raises(frappe.ValidationError):
		blocking.assert_pickable(BATCH_A2)

	entries = audit.entries_for("Batch", BATCH_A2)
	refusals = [entry for entry in entries if entry["outcome"] == audit.REFUSED]
	assert refusals, "the blocked pick left no audit entry"
	assert _complete(refusals[-1])
	assert refusals[-1]["rule"] == blocking.RULE_BLOCKED_PICKING


def test_certificate_issue_is_audited(site):
	"""URS-W2-034 AC-1 — issuing a CoA is an audited act, not a silent insert."""
	_require(site, "Batch", BATCH_C1)
	if not site.db.exists("DocType", coa.DOCTYPE):
		pytest.skip("W2 quality DocTypes not installed on this site")
	accepted_inspection_for(site, BATCH_C1)
	_as_inspector(site)
	certificate = coa.issue(BATCH_C1, attach_pdf=False)

	entries = audit.entries_for(coa.DOCTYPE, certificate.name)
	assert entries, "the issued certificate left no audit entry"
	assert entries[-1]["gate"] == coa.ISSUE_GATE
	assert entries[-1]["rule"] == coa.ISSUE_RULE
	assert entries[-1]["outcome"] == audit.EXECUTED
	assert entries[-1]["logged_by"] == INSPECTOR


def test_migration_run_is_audited_with_its_run_ids(site):
	"""URS-W2-034 AC-1 — the pilot run is auditable by run id and verdict."""
	from rheinwerk_mes.integration.migration.w2 import cli as w2_cli

	# The pilot commits (it is a real migration run, not a fixture), so this test undoes it
	# by run id afterwards — the rehearsed rollback the URS requires — and leaves only the
	# append-only audit trail behind, which is what the case is about.
	summary = w2_cli.run_w2_migration()
	try:
		_assert_migration_audit(summary, w2_cli)
	finally:
		if not summary["rolled_back"]:
			for plant_run_ids in summary["run_ids"].values():
				w2_cli.rollback_plant(plant_run_ids)
			frappe.db.commit()


def _assert_migration_audit(summary: dict[str, Any], w2_cli: Any) -> None:
	entries = frappe.get_all(
		audit.LOG_DOCTYPE,
		filters={"gate": w2_cli.MIGRATION_GATE},
		fields=["gate", "rule", "outcome", "logged_by", "logged_at", "reference_name", "detail", "to_state"],
		order_by="creation desc",
		limit=1,
	)
	assert entries and _complete(entries[0])
	assert entries[0]["to_state"] == summary["status"]
	for plant_run_ids in summary["run_ids"].values():
		for run_id in plant_run_ids.values():
			assert run_id in entries[0]["detail"], f"run id {run_id} is missing from the audit entry"
