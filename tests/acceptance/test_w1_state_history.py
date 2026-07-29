"""TC-W1-003 — `state_history` audit rows and mandatory reasons (URS-W1-003).

Two layers: offline contracts on the committed schema and rule surface, then the
site-backed TC-W1-003 steps of `docs/test/TST-W1-production-core.md`, which skip
(never fail) when the Frappe substrate or the programme fixtures are absent.

Legacy baseline (semantics only, never ported): Qcadoo
`orders/model/orderStateChange.xml:36-47` and `reasonTypeOfChangingOrderState.xml`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")
w1_state_audit = pytest.importorskip("rheinwerk_mes.setup.w1_state_audit")

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"
OPERATOR_USER = "o.weber@rheinwerk-chemie.example"

DOCTYPE_JSON = Path("rheinwerk_mes/manufacturing_core/doctype/order_state_history/order_state_history.json")


# --------------------------------------------------------------------------------------
# Offline contracts
# --------------------------------------------------------------------------------------


def test_audit_row_schema_is_a_read_only_child_table(repo_root):
	"""URS-W1-003: the audit row carries state, user, timestamp and reason, and no
	field is editable from the Desk."""
	child = json.loads((repo_root / DOCTYPE_JSON).read_text())
	assert child["istable"] == 1
	assert child["module"] == "Manufacturing Core"
	assert child["sort_field"] == "creation" and child["sort_order"] == "ASC"
	fields = {field["fieldname"]: field for field in child["fields"] if field["fieldtype"] != "Column Break"}
	assert set(fields) >= {"from_state", "to_state", "changed_by", "changed_at", "reason"}
	assert fields["to_state"]["reqd"] == 1
	assert all(field.get("read_only") == 1 for field in fields.values())


def test_reason_is_required_for_exactly_the_qcadoo_reason_states():
	"""URS-W1-003 / `reasonTypeOfChangingOrderState.xml` — Declined, Abandoned, Interrupted."""
	assert exec_state.REASON_REQUIRED_STATES == {
		exec_state.DECLINED,
		exec_state.ABANDONED,
		exec_state.INTERRUPTED,
	}
	assert all(state in exec_state.STATES for state in exec_state.REASON_REQUIRED_STATES)
	assert not any(
		exec_state.requires_reason(state)
		for state in (exec_state.PENDING, exec_state.ACCEPTED, exec_state.IN_PROGRESS, exec_state.COMPLETED)
	)


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_blank_reasons_do_not_satisfy_a_reason_required_state(reason):
	"""URS-W1-003 AC-2: whitespace is not a reason."""
	assert not exec_state.is_reason_satisfied(exec_state.DECLINED, reason)
	assert exec_state.is_reason_satisfied(exec_state.ACCEPTED, reason)


def test_history_row_carries_state_user_timestamp_and_trimmed_reason():
	"""URS-W1-003 AC-1/AC-2: the recorded row shape."""
	changed_at = datetime(2026, 3, 10, 8, 30)
	row = exec_state.build_history_row(
		exec_state.PENDING, exec_state.DECLINED, PLANNER_USER, changed_at, "  Kunde storniert  "
	)
	assert row == {
		"from_state": exec_state.PENDING,
		"to_state": exec_state.DECLINED,
		"changed_by": PLANNER_USER,
		"changed_at": changed_at,
		"reason": "Kunde storniert",
	}
	assert (
		exec_state.build_history_row(exec_state.PENDING, exec_state.ACCEPTED, PLANNER_USER, changed_at, "  ")[
			"reason"
		]
		is None
	)


def _raise_validation_error(message: str, title: str | None = None) -> None:
	"""Stand-in for `frappe.throw`, which needs a site to render its message."""
	raise frappe.ValidationError(message)


class _StubOrder:
	"""The slice of the Work Order document surface the audit funnel touches."""

	def __init__(self, name: str, exec_state_value: str, reason: str | None = None):
		self.name = name
		self.exec_state = exec_state_value
		self.exec_state_reason = reason
		self.state_history: list[dict[str, Any]] = []
		self.flags = frappe._dict()
		self.meta = frappe._dict(has_field=lambda fieldname: fieldname in self._fieldnames())

	@staticmethod
	def _fieldnames() -> set[str]:
		return {exec_state.STATE_FIELD, exec_state.REASON_FIELD, exec_state.HISTORY_FIELD}

	def get(self, fieldname: str, default: Any = None) -> Any:
		return getattr(self, fieldname, default)

	def append(self, fieldname: str, row: dict[str, Any]) -> None:
		getattr(self, fieldname).append(row)


@pytest.fixture
def funnel(monkeypatch):
	"""`record_exec_state_change` with the stored state and clock under test control."""
	stored: dict[str, str] = {}
	monkeypatch.setattr(exec_state, "_", lambda message: message)
	monkeypatch.setattr(exec_state, "now_datetime", lambda: datetime(2026, 3, 10, 8, 30))
	monkeypatch.setattr(
		exec_state.frappe,
		"db",
		frappe._dict(
			exists=lambda doctype, name: name in stored,
			get_value=lambda doctype, name, fieldname: stored.get(name),
		),
	)
	monkeypatch.setattr(exec_state.frappe, "session", frappe._dict(user=PLANNER_USER))
	monkeypatch.setattr(exec_state.frappe, "throw", _raise_validation_error)
	return stored


def test_funnel_records_one_row_per_state_change(funnel):
	"""URS-W1-003 AC-1 — the funnel appends state, user, timestamp for a real change."""
	funnel[FIRST_ORDER] = exec_state.PENDING
	order = _StubOrder(FIRST_ORDER, exec_state.ACCEPTED)

	exec_state.record_exec_state_change(order)

	assert order.state_history == [
		exec_state.build_history_row(
			exec_state.PENDING, exec_state.ACCEPTED, PLANNER_USER, datetime(2026, 3, 10, 8, 30)
		)
	]


def test_funnel_ignores_saves_that_do_not_change_the_state(funnel):
	"""URS-W1-003 — a save that leaves `exec_state` alone writes no audit row."""
	funnel[FIRST_ORDER] = exec_state.ACCEPTED
	order = _StubOrder(FIRST_ORDER, exec_state.ACCEPTED)

	exec_state.record_exec_state_change(order)

	assert order.state_history == []


def test_funnel_refuses_a_reason_required_change_without_a_reason(funnel):
	"""URS-W1-003 AC-2 — refusal names the state and the order, and records nothing."""
	funnel[SECOND_ORDER] = exec_state.PENDING
	order = _StubOrder(SECOND_ORDER, exec_state.DECLINED)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.record_exec_state_change(order)
	assert exec_state.DECLINED in str(excinfo.value) and SECOND_ORDER in str(excinfo.value)
	assert order.state_history == []

	order.flags.exec_state_reason = "Kunde storniert"
	exec_state.record_exec_state_change(order)
	assert order.state_history[-1]["reason"] == "Kunde storniert"


# --------------------------------------------------------------------------------------
# Site-backed TC-W1-003
# --------------------------------------------------------------------------------------


def test_audit_fields_extend_the_anchor_as_custom_fields(site):
	"""URS-W1-003: `exec_state` and `state_history` live on the unforked anchor, and
	both survive submit so an audited order can still change state."""
	fields = {field["fieldname"]: field for field in w1_state_audit.custom_field_definitions()["Work Order"]}
	assert fields["exec_state"]["options"].split("\n") == list(exec_state.STATES)
	assert fields["exec_state"]["default"] == exec_state.INITIAL_STATE
	assert fields["state_history"]["options"] == "Order State History"
	assert fields["state_history"]["read_only"] == 1
	for fieldname in ("exec_state", "exec_state_reason", "state_history"):
		assert fields[fieldname]["allow_on_submit"] == 1
		assert fields[fieldname]["module"] == w1_state_audit.MANUFACTURING_CORE
	anchor_module = site.db.get_value("DocType", "Work Order", "module")
	assert site.db.get_value("Module Def", anchor_module, "app_name") == "erpnext"
	assert site.get_meta("Work Order").get_field("state_history").options == "Order State History"
	for fieldname in fields:
		assert not site.db.exists("DocField", {"parent": "Work Order", "fieldname": fieldname})


def _seeded_order(site: Any, name: str = FIRST_ORDER, state: str = exec_state.PENDING) -> Any:
	"""The seeded production order, submitted and forced into a known `exec_state`."""
	if not site.db.exists("Work Order", name):
		pytest.skip(f"programme fixture {name} not seeded on this site")
	doc = site.get_doc("Work Order", name)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	site.db.set_value("Work Order", name, exec_state.STATE_FIELD, state, update_modified=False)
	site.db.delete("Order State History", {"parent": name})
	doc.reload()
	return doc


def _acting_user(site: Any, user: str) -> str:
	"""Act as `user` when the fixture user exists, else stay Administrator."""
	if site.db.exists("User", user):
		site.set_user(user)
	return site.session.user


def test_tc_w1_003_step_1_rows_users_and_timestamps(site):
	"""URS-W1-003 AC-1 — Pending→Accepted→In Progress leaves two ordered rows."""
	order = _seeded_order(site)

	planner = _acting_user(site, PLANNER_USER)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	operator = _acting_user(site, OPERATOR_USER)
	exec_state.transition(order.name, exec_state.IN_PROGRESS)
	site.set_user("Administrator")

	rows = exec_state.state_history(order.name)
	assert [(row["from_state"], row["to_state"]) for row in rows] == [
		(exec_state.PENDING, exec_state.ACCEPTED),
		(exec_state.ACCEPTED, exec_state.IN_PROGRESS),
	]
	assert [row["changed_by"] for row in rows] == [planner, operator]
	assert rows[0]["changed_at"] <= rows[1]["changed_at"]
	assert all(row["reason"] is None for row in rows)


def test_tc_w1_003_step_2_decline_without_reason_is_refused(site):
	"""URS-W1-003 AC-2 — Declined needs a reason; with one the reason is stored."""
	order = _seeded_order(site, SECOND_ORDER)
	_acting_user(site, PLANNER_USER)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order.name, exec_state.DECLINED)
	assert "Begründung" in str(excinfo.value)
	assert exec_state.state_history(order.name) == []

	exec_state.transition(order.name, exec_state.DECLINED, reason="Kunde storniert")
	rows = exec_state.state_history(order.name)
	assert len(rows) == 1
	assert rows[-1]["to_state"] == exec_state.DECLINED
	assert rows[-1]["reason"] == "Kunde storniert"


@pytest.mark.parametrize("target", [exec_state.ABANDONED, exec_state.INTERRUPTED])
def test_tc_w1_003_reason_enforcement_covers_abandoned_and_interrupted(site, target):
	"""URS-W1-003 — the same rule holds for the other reason-required states."""
	order = _seeded_order(site, SECOND_ORDER, state=exec_state.IN_PROGRESS)

	with pytest.raises(frappe.ValidationError):
		exec_state.transition(order.name, target)

	exec_state.transition(order.name, target, reason="Rohstoff fehlt")
	assert exec_state.state_history(order.name)[-1]["reason"] == "Rohstoff fehlt"
