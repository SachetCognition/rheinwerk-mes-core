"""W1-2 — immutable audit of every gated action (URS-W1-033 · TC-W1-036).

Step 1: the TC-W1-006 refusal appears in the order's audit view with the gate name, the
missing field, the user and the timestamp — readable by the QA persona (B. Vogel).
Step 2: modifying (or deleting) that entry through the API is refused.

Executed transitions are logged as well, so the audit view of an order tells the whole
story: which gate refused what, and which transitions actually happened.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

from test_w1_gating_support import (  # noqa: E402  (import after the substrate check)
	LINE,
	RECIPE,
	SECOND_ORDER,
	set_fields,
	set_governance_state,
	submitted_order,
)

QA_USER = "b.vogel@rheinwerk-chemie.example"


def _trigger_acceptance_refusal(site) -> str:
	"""Arrange and trigger the TC-W1-006 refusal; returns the order name."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(site, order, production_line=None, planned_end_date="2026-03-12 14:00:00")
	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order, exec_state.ACCEPTED)
	return order.name


def test_refusal_is_logged_with_gate_record_user_and_timestamp(site):
	"""URS-W1-033 · TC-W1-036 step 1 — the refusal row carries the full audit tuple."""
	order = _trigger_acceptance_refusal(site)

	entries = [e for e in audit.entries_for("Work Order", order) if e["outcome"] == audit.REFUSED]
	assert entries, "the refusal must be logged"
	entry = entries[-1]
	assert entry["gate"] == "acceptance_gate"
	assert entry["rule"]
	assert "Fertigungslinie" in entry["detail"], "the refused field is named in the audit row"
	assert entry["logged_by"] == "Administrator"
	assert entry["logged_at"] is not None
	assert entry["to_state"] == exec_state.ACCEPTED


def test_audit_view_is_readable_by_qa(site):
	"""URS-W1-033 · TC-W1-036 step 1 — QA can read the order's audit view."""
	order = _trigger_acceptance_refusal(site)
	if not site.db.exists("User", QA_USER):
		pytest.skip("QA persona not seeded on this site")

	site.set_user(QA_USER)
	try:
		rows = site.get_all(
			audit.LOG_DOCTYPE,
			filters={"reference_doctype": "Work Order", "reference_name": order},
			fields=["gate", "outcome", "logged_by"],
		)
	finally:
		site.set_user("Administrator")

	assert rows, "the audit view must be readable by the QA role"


def test_audit_entry_cannot_be_modified(site):
	"""URS-W1-033 · TC-W1-036 step 2 — editing a logged entry through the API is refused."""
	order = _trigger_acceptance_refusal(site)
	name = audit.entries_for("Work Order", order)[-1]["name"]

	entry = site.get_doc(audit.LOG_DOCTYPE, name)
	entry.detail = "manipuliert"
	with pytest.raises(frappe.PermissionError):
		entry.save(ignore_permissions=True)

	assert site.db.get_value(audit.LOG_DOCTYPE, name, "detail") != "manipuliert"


def test_audit_entry_cannot_be_deleted(site):
	"""URS-W1-033 · TC-W1-036 step 2 — deleting a logged entry is refused as well."""
	order = _trigger_acceptance_refusal(site)
	name = audit.entries_for("Work Order", order)[-1]["name"]

	with pytest.raises(frappe.PermissionError):
		site.delete_doc(audit.LOG_DOCTYPE, name, force=True, ignore_permissions=True)

	assert site.db.exists(audit.LOG_DOCTYPE, name)


def test_executed_transition_is_logged(site):
	"""URS-W1-033 — passing transitions are logged too, not only refusals."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date="2026-03-10 06:00:00",
		planned_end_date="2026-03-12 14:00:00",
	)
	set_governance_state(site, RECIPE, "Accepted")

	exec_state.transition(order, exec_state.ACCEPTED)

	executed = [e for e in audit.entries_for("Work Order", order.name) if e["outcome"] == audit.EXECUTED]
	assert len(executed) == 1
	assert executed[0]["from_state"] == exec_state.PENDING
	assert executed[0]["to_state"] == exec_state.ACCEPTED
	assert executed[0]["logged_by"] == "Administrator"


def test_transition_logging_is_idempotent(site):
	"""URS-W1-033 — re-saving the order does not duplicate the transition entry."""
	order = submitted_order(site, SECOND_ORDER)
	set_fields(
		site,
		order,
		production_line=LINE,
		planned_start_date="2026-03-10 06:00:00",
		planned_end_date="2026-03-12 14:00:00",
	)
	set_governance_state(site, RECIPE, "Accepted")
	exec_state.transition(order, exec_state.ACCEPTED)

	order.reload()
	order.save()

	executed = [e for e in audit.entries_for("Work Order", order.name) if e["outcome"] == audit.EXECUTED]
	assert len(executed) == 1


def test_gate_log_is_declared_append_only(site):
	"""URS-W1-033 — the DocType itself is submit-free and in_create (installer contract)."""
	w1_gating = pytest.importorskip("rheinwerk_mes.setup.w1_gating")
	w1_gating.assert_gate_log_is_append_only()

	meta = frappe.get_meta(audit.LOG_DOCTYPE)
	assert meta.in_create
	assert not meta.is_submittable
	assert all(not perm.get("write") and not perm.get("delete") for perm in meta.permissions)
