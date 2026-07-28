"""TC-W2-009 / TC-W2-010 — the `qa_state` workflow (W2-2).

Verifies **URS-W2-006 AC-1…5**: Quarantined entry state, auditing of every disposition with
user/timestamp/reason/trigger, the mandatory reason on Blocked and Released, the refusal of
illegal transitions naming the legal ones, the quality-inspector role gate (AC-4, overlapping
URS-W2-036) and the gate-registration mechanism the W2-4 quality child hooks its Quality
Inspection outcome into.
"""

from __future__ import annotations

import pytest
from test_w2_genealogy_support import BATCH_A2, BATCH_C1, require_fixture, require_w2_schema, set_state

frappe = pytest.importorskip("frappe")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")

OPERATOR = "o.weber@rheinwerk-chemie.example"
INSPECTOR = "q.fischer@rheinwerk-chemie.example"


@pytest.fixture
def batch(site):
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A2)
	set_state(site, BATCH_A2, qa_state.QUARANTINED)
	site.db.delete("Batch QA State History", {"parent": BATCH_A2})
	yield BATCH_A2
	site.set_user("Administrator")


def test_produced_batch_enters_quarantined(site):
	"""URS-W2-006 AC-1 / TC-W2-009 step 1 — the entry state needs no explicit setting."""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	doc = site.get_doc(
		{
			"doctype": "Batch",
			"batch_id": "BATCH-C-9002",
			"item": "RW-CHM-0003",
			"manufacturing_date": "2026-04-01",
			"expiry_date": "2027-04-01",
		}
	).insert(ignore_permissions=True)
	assert doc.qa_state == qa_state.QUARANTINED


def test_release_is_audited_with_user_timestamp_reason_and_trigger(site, batch):
	"""URS-W2-006 AC-2/AC-5 / TC-W2-009 step 2 — the audit row carries the full context."""
	qa_state.transition(batch, qa_state.RELEASED, reason="QI angenommen", triggering_document="QI-2026-0001")

	history = qa_state.state_history(batch)
	assert site.db.get_value("Batch", batch, "qa_state") == qa_state.RELEASED
	assert len(history) == 1
	row = history[0]
	assert (row["from_state"], row["to_state"]) == (qa_state.QUARANTINED, qa_state.RELEASED)
	assert row["reason"] == "QI angenommen" and row["triggering_document"] == "QI-2026-0001"
	assert row["changed_by"] == frappe.session.user and row["changed_at"]


def test_blocking_without_reason_is_refused_and_with_reason_is_audited(site, batch):
	"""URS-W2-006 AC-3 / TC-W2-009 step 3 — the reason gate refuses, then the block lands."""
	with pytest.raises(frappe.ValidationError) as refusal:
		qa_state.transition(batch, qa_state.BLOCKED)
	assert "Begründung" in str(refusal.value)
	assert site.db.get_value("Batch", batch, "qa_state") == qa_state.QUARANTINED

	qa_state.transition(batch, qa_state.BLOCKED, reason="Lieferantenrückruf K7/2026-06")

	assert site.db.get_value("Batch", batch, "qa_state") == qa_state.BLOCKED
	assert qa_state.state_history(batch)[-1]["reason"] == "Lieferantenrückruf K7/2026-06"


def test_illegal_transition_is_rejected_naming_the_allowed_targets(site, batch):
	"""URS-W2-006 AC-1 / TC-W2-009 step 4 — Released → Quarantined is not a legal edge."""
	set_state(site, batch, qa_state.RELEASED)

	with pytest.raises(frappe.ValidationError) as refusal:
		qa_state.transition(batch, qa_state.QUARANTINED, reason="Rückstufung")

	message = str(refusal.value)
	assert "Gesperrt" in message, "the refusal names the legal targets"
	assert qa_state.allowed_targets(qa_state.RELEASED) == frozenset({qa_state.BLOCKED})


def test_operator_may_not_dispose_but_the_quality_inspector_may(site, batch):
	"""URS-W2-006 AC-4 / TC-W2-010 steps 1-2 — role gate refuses, inspector succeeds."""
	if not site.db.exists("User", OPERATOR) or not site.db.exists("User", INSPECTOR):
		pytest.skip("persona fixtures not seeded on this site")
	set_state(site, batch, qa_state.BLOCKED)

	site.set_user(OPERATOR)
	with pytest.raises(frappe.PermissionError):
		qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe durch Bediener")
	assert site.db.get_value("Batch", batch, "qa_state") == qa_state.BLOCKED

	site.set_user("Administrator")
	site.get_doc("User", INSPECTOR).add_roles("Quality Manager")
	site.set_user(INSPECTOR)
	qa_state.transition(batch, qa_state.RELEASED, reason="Nachprüfung bestanden")
	assert site.db.get_value("Batch", batch, "qa_state") == qa_state.RELEASED


def refusing_gate(context):
	"""Stand-in for the W2-4 Quality-Inspection gate, registered through the hook."""
	context.refuse("Testtor: QI fehlt")


def test_sibling_modules_register_gates_through_the_hook(site, batch, monkeypatch):
	"""URS-W2-006 AC-5 — the W1 `exec_state` gate pattern, reused for dispositions.

	The quality child (W2-4) registers its Quality-Inspection gate under
	`rheinwerk_qa_state_gates` instead of editing the genealogy module; the hook is
	exercised here with a temporary gate so the mechanism itself is pinned.
	"""
	assert "rheinwerk_mes.genealogy.qa_state.reason_gate" in frappe.get_hooks(qa_state.GATE_HOOK)

	registered = frappe.get_hooks(qa_state.GATE_HOOK)
	monkeypatch.setattr(
		qa_state,
		"_gate_callables",
		lambda: [frappe.get_attr(path) for path in registered] + [refusing_gate],
	)

	with pytest.raises(frappe.ValidationError) as refusal:
		qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe")
	assert "Testtor: QI fehlt" in str(refusal.value)
