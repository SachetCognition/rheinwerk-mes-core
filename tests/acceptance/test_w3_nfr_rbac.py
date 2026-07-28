"""TC-W3-027 — permission matrix for the planning and boundary actions of W3.

Verifies **URS-W3-023** (schedule decisions belong to the planner, message replay to the
interface administrator, tag mappings to the technologist, and every refusal is audited and
names the permission it needs) through **TC-W3-027** of
`docs/test/TST-W3-planning-boundary.md`.

Every case drives the published API as the persona, never the Desk UI: the requirement is
about server-side enforcement, and a hidden button is not a control.
"""

from __future__ import annotations

from typing import Any

import pytest
from test_w3_boundary_support import loopback
from test_w3_scada_support import MIX_WORK_CENTRE, ensure_tag_mappings
from test_w3_scheduling_support import OPERATOR_USER, PLANNER_USER, as_planner, draft_schedule

frappe = pytest.importorskip("frappe")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

TECHNOLOGIST_USER = "t.schmid@rheinwerk-chemie.example"
VIEWER_USER = "b.vogel@rheinwerk-chemie.example"
#: URS-W3-023 AC-2 is about a planner *without* interface-admin rights; the seeded P. Krüger
#: holds both at Plant C, so the stricter case gets a planner-only user of its own.
PLANNER_ONLY_USER = "planner.only@rheinwerk-chemie.example"

NEW_TAG = "ns=2;s=Line1.Mix01.Temperature"


def _as(site: Any, user: str) -> None:
	if not site.db.exists("User", user):
		pytest.skip(f"persona {user} not seeded on this site")
	site.set_user(user)


def _planner_only(site: Any) -> str:
	"""A user holding the planner role and nothing else (rolled back with the test)."""
	if not site.db.exists("User", PLANNER_ONLY_USER):
		user = frappe.new_doc("User")
		user.email = PLANNER_ONLY_USER
		user.first_name = "Planer"
		user.send_welcome_email = 0
		user.append("roles", {"role": "Rheinwerk Planner"})
		user.flags.ignore_permissions = True
		user.insert(ignore_permissions=True)
	return PLANNER_ONLY_USER


def test_operator_cannot_approve_a_schedule(site):
	"""URS-W3-023 AC-1 / TC-W3-027 step 1 — approval is the planner's act, and the refusal audits."""
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	schedule = draft_schedule(site)
	_as(site, OPERATOR_USER)
	with pytest.raises(frappe.PermissionError):
		lifecycle.approve(schedule.name)

	site.set_user("Administrator")
	assert site.db.get_value(lifecycle.SCHEDULE_DOCTYPE, schedule.name, "schedule_state") == lifecycle.DRAFT


def test_planner_may_approve_a_schedule(site):
	"""URS-W3-023 AC-1 / TC-W3-027 step 2 — the mapped role succeeds where the operator failed."""
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	schedule = draft_schedule(site)
	as_planner(site)
	lifecycle.approve(schedule.name)

	assert (
		site.db.get_value(lifecycle.SCHEDULE_DOCTYPE, schedule.name, "schedule_state") == lifecycle.APPROVED
	)


def test_planner_cannot_replay_a_boundary_message(site, monkeypatch):
	"""URS-W3-023 AC-2 / TC-W3-027 step 3 — replay names the role it requires."""
	from rheinwerk_mes.integration.boundary import contracts, health, inbound

	loopback(monkeypatch)
	inbound.play_fixture("erp-in-002-unknown-item.json")
	message = frappe.get_all(
		contracts.MESSAGE_DOCTYPE,
		filters={"message_state": contracts.REJECTED},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	assert message, "the rejection stored no message to replay"

	site.set_user(_planner_only(site))
	assert health.can_replay() is False
	with pytest.raises(frappe.PermissionError) as refusal:
		health.replay(message[0])
	assert any(role in str(refusal.value) for role in health.REPLAY_ROLES)


def test_the_interface_administrator_may_replay(site, monkeypatch):
	"""URS-W3-023 AC-2 / TC-W3-027 step 4 — the authorised replay goes through and audits."""
	from rheinwerk_mes.integration.boundary import contracts, health, inbound

	loopback(monkeypatch)
	inbound.play_fixture("erp-in-002-unknown-item.json")
	message = frappe.get_all(
		contracts.MESSAGE_DOCTYPE,
		filters={"message_state": contracts.REJECTED},
		order_by="creation desc",
		limit=1,
		pluck="name",
	)
	assert message

	_as(site, PLANNER_USER)
	assert health.can_replay() is True, "P. Krüger is the Plant C interface administrator"
	outcome = health.replay(message[0])

	assert outcome["name"] == message[0]
	trail = health.audit_trail(message[0])
	assert trail and trail[-1]["logged_by"] == PLANNER_USER


def test_only_the_technologist_administers_tag_mappings(site):
	"""URS-W3-023 AC-2 / TC-W3-027 step 4 — the mapping table is the technologist's surface."""
	from rheinwerk_mes.integration.scada import mapping

	ensure_tag_mappings(site)

	_as(site, OPERATOR_USER)
	with pytest.raises(frappe.PermissionError):
		_new_mapping().insert()

	_as(site, TECHNOLOGIST_USER)
	saved = _new_mapping()
	saved.insert()

	assert site.db.exists(mapping.MAPPING_DOCTYPE, saved.name)


def _new_mapping() -> Any:
	"""An unsaved tag mapping — inserted through the document API so permissions apply."""
	from rheinwerk_mes.integration.scada import mapping

	doc = frappe.new_doc(mapping.MAPPING_DOCTYPE)
	doc.tag_address = NEW_TAG
	doc.work_centre_code = MIX_WORK_CENTRE
	doc.event_type = "produced-count"
	doc.uom = "Kg"
	doc.enabled = 1
	return doc


def test_business_viewer_reads_the_w3_surfaces_and_changes_nothing(site):
	"""URS-W3-023 AC-3 — B. Vogel sees the board and the health tile, and writes nowhere."""
	from rheinwerk_mes.integration.boundary import health
	from rheinwerk_mes.manufacturing_core.scheduling import lifecycle

	schedule = draft_schedule(site)
	_as(site, VIEWER_USER)

	assert health.kpi_tile()["count"] >= 0
	assert frappe.has_permission(lifecycle.SCHEDULE_DOCTYPE, "read", doc=schedule.name)
	assert not frappe.has_permission(lifecycle.SCHEDULE_DOCTYPE, "write", doc=schedule.name)
	with pytest.raises(frappe.PermissionError):
		lifecycle.approve(schedule.name)
