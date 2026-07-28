"""TC-W2-020 / TC-W2-021 — QI gating of the `exec_state` machine (W2-4).

Verifies **URS-W2-014 AC-1…3**: completion of a production order is refused while a
produced batch has no submitted Accepted inspection or carries a Rejected one — naming rule,
record and resolution, leaving `exec_state` untouched and writing the refusal to the W1 gate
log — and an Accepted inspection releases its batch through the genealogy API so completion
proceeds. The gate is registered through the documented `rheinwerk_exec_state_gates` hook;
`manufacturing_core` is not edited.
"""

from __future__ import annotations

import pytest
from test_w2_quality_support import (
	BATCH_C1,
	FAILING_READINGS,
	FIRST_ORDER,
	PASSING_READINGS,
	TEMPLATE,
	inspection_for,
	require_fixture,
	require_quality_schema,
	set_qa_state,
)

pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
gates = pytest.importorskip("rheinwerk_mes.quality.gates")
inspections = pytest.importorskip("rheinwerk_mes.quality.inspections")
hooks = pytest.importorskip("rheinwerk_mes.hooks")


@pytest.fixture
def order_in_progress(site):
	"""PO-2026-0001 In Progress with its produced batch back in Quarantine."""
	require_quality_schema(site)
	doc = require_fixture(site, "Work Order", FIRST_ORDER)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
		doc.reload()
	site.db.set_value("Work Order", FIRST_ORDER, "exec_state", exec_state.IN_PROGRESS, update_modified=False)
	site.db.delete("Order State History", {"parent": FIRST_ORDER})
	site.db.delete("Execution Gate Log", {"reference_name": FIRST_ORDER})
	# The W1 completion gate wants recorded output; this suite is about the QI gate.
	site.db.set_value("Work Order", FIRST_ORDER, "produced_qty", doc.qty, update_modified=False)
	set_qa_state(site, BATCH_C1, qa_state.QUARANTINED)
	if not inspections.produced_batches(FIRST_ORDER):
		pytest.skip("genealogy fixture (PO-2026-0001 → BATCH-C-1001) not seeded on this site")
	doc.reload()
	return doc


def test_gate_is_registered_through_the_documented_hook():
	"""URS-W2-014 AC-1 — registration only; `manufacturing_core` stays untouched."""
	assert "rheinwerk_mes.quality.gates.quality_inspection_gate" in hooks.rheinwerk_exec_state_gates


def test_completion_without_an_inspection_is_refused_naming_rule_record_resolution(order_in_progress):
	"""URS-W2-014 AC-1 / TC-W2-020 step 1 — refusal names order, batch and template."""
	with pytest.raises(Exception) as refusal:
		exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Fertig")

	message = str(refusal.value)
	assert gates.QI_REQUIRED_RULE in message
	for record in (FIRST_ORDER, BATCH_C1, TEMPLATE):
		assert record in message


def test_refused_completion_leaves_exec_state_in_progress(order_in_progress, site):
	"""URS-W2-014 AC-1 / TC-W2-020 step 1 — the refusal has no side effect on the state."""
	with pytest.raises(Exception):
		exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Fertig")

	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.IN_PROGRESS


def test_refusal_is_written_to_the_w1_execution_gate_log(order_in_progress, site):
	"""URS-W2-014 AC-1 — the refusal is auditable through the existing gate log."""
	with pytest.raises(Exception):
		exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Fertig")

	logged = site.get_all(
		"Execution Gate Log",
		filters={"reference_name": FIRST_ORDER, "gate": "quality_inspection_gate"},
		fields=["rule", "to_state"],
	)
	assert logged and logged[0]["to_state"] == exec_state.COMPLETED


def test_draft_inspection_does_not_satisfy_the_gate(order_in_progress):
	"""URS-W2-014 AC-1 — readings entered but not submitted are not evidence."""
	inspection_for(order_in_progress, BATCH_C1, PASSING_READINGS, work_order=FIRST_ORDER)

	with pytest.raises(Exception) as refusal:
		exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Fertig")
	assert gates.QI_REQUIRED_RULE in str(refusal.value)


def test_rejected_inspection_refusal_names_the_rejected_inspection(order_in_progress):
	"""URS-W2-014 AC-2 / TC-W2-020 step 2 — the refusal points at the Rejected document."""
	doc = inspection_for(order_in_progress, BATCH_C1, FAILING_READINGS, submit=True, work_order=FIRST_ORDER)

	with pytest.raises(Exception) as refusal:
		exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Fertig")
	message = str(refusal.value)
	assert gates.QI_REJECTED_RULE in message and doc.name in message


def test_accepted_inspection_releases_the_batch_through_the_genealogy_api(order_in_progress, site):
	"""URS-W2-014 AC-3 / TC-W2-021 step 1 — release is audited to the inspection."""
	doc = inspection_for(order_in_progress, BATCH_C1, PASSING_READINGS, submit=True, work_order=FIRST_ORDER)

	assert site.db.get_value("Batch", BATCH_C1, "qa_state") == qa_state.RELEASED
	history = qa_state.state_history(BATCH_C1)
	assert history[-1]["to_state"] == qa_state.RELEASED
	assert history[-1]["triggering_document"] == doc.name


def test_completion_proceeds_once_the_inspection_is_accepted(order_in_progress, site):
	"""URS-W2-014 AC-3 / TC-W2-021 step 2 — the order completes and the transition is kept."""
	inspection_for(order_in_progress, BATCH_C1, PASSING_READINGS, submit=True, work_order=FIRST_ORDER)

	exec_state.transition(FIRST_ORDER, exec_state.COMPLETED, reason="Charge freigegeben")

	assert site.db.get_value("Work Order", FIRST_ORDER, "exec_state") == exec_state.COMPLETED
