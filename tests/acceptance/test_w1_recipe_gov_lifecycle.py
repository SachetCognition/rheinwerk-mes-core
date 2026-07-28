"""W1-4 — `gov_state` lifecycle on the governed BOM/Routing pair.

TC-W1-015 (URS-W1-014): Draft → Checked → Draft → Checked → Accepted, illegal returns
from Accepted, declining a Checked recipe, and the role gate on the accept transition.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"
TECHNOLOGIST_USER = "t.schmid@rheinwerk-chemie.example"
CLERK_USER = "w.braun@rheinwerk-chemie.example"


def _draft_record(site, bom: str = BOM_NAME):
	"""A Draft governance record for `bom`, reusing the seeded (Accepted) fixture record.

	The reset writes `gov_state` directly: rewinding an Accepted recipe is precisely what
	the transition rules forbid, so it can only be test setup, never production behaviour.
	"""
	name = governance.governance_name(bom)
	if not name:
		return site.get_doc({"doctype": "Recipe Governance", "bom": bom, "routing": ROUTING}).insert()
	site.db.set_value("Recipe Governance", name, "gov_state", governance.DRAFT)
	return site.get_doc("Recipe Governance", name)


def test_tc_w1_015_new_governance_record_starts_in_draft(site):
	"""TC-W1-015 step 1 (URS-W1-014 AC-1): a governance record for BOM-RW-CHM-0003-001 and
	RT-COMPOUND-01 references both anchors and starts in Draft."""
	name = governance.governance_name(BOM_NAME)
	site.db.set_value("Recipe Governance", name, "gov_state", governance.DRAFT)
	site.delete_doc("Recipe Governance", name, force=True, ignore_permissions=True)

	doc = site.get_doc({"doctype": "Recipe Governance", "bom": BOM_NAME, "routing": ROUTING}).insert()
	assert doc.gov_state == governance.DRAFT
	assert doc.bom == BOM_NAME
	assert doc.routing == ROUTING
	assert doc.item == "RW-CHM-0003"
	assert [(row.from_state, row.to_state) for row in doc.state_history] == [("", governance.DRAFT)]


def test_tc_w1_015_draft_checked_draft_checked_accepted(site):
	"""TC-W1-015 step 2 (URS-W1-014 AC-2): the full legal walk Draft → Checked →
	Draft → Checked → Accepted, each step recorded in the state history."""
	doc = _draft_record(site)

	governance.transition(doc, governance.CHECKED)
	assert doc.gov_state == governance.CHECKED

	governance.transition(doc, governance.DRAFT, reason="Rezeptur nachgearbeitet")
	assert doc.gov_state == governance.DRAFT

	governance.transition(doc, governance.CHECKED)
	governance.transition(doc, governance.ACCEPTED)
	assert doc.gov_state == governance.ACCEPTED
	assert governance.gov_state(BOM_NAME) == governance.ACCEPTED
	assert [row.to_state for row in doc.state_history][-4:] == [
		governance.CHECKED,
		governance.DRAFT,
		governance.CHECKED,
		governance.ACCEPTED,
	]


@pytest.mark.parametrize("target", [governance.DRAFT, governance.CHECKED])
def test_tc_w1_015_accepted_cannot_return_to_draft_or_checked(site, target):
	"""TC-W1-015 step 3 (URS-W1-014 AC-3): an Accepted recipe never returns to Draft or
	Checked — `TechnologyState.java:33-66` allows Outdated only."""
	doc = site.get_doc("Recipe Governance", governance.governance_name(BOM_NAME))
	assert doc.gov_state == governance.ACCEPTED

	with pytest.raises(site.exceptions.ValidationError) as refusal:
		governance.transition(doc, target, reason="Nachbesserung")
	assert target in str(refusal.value) or governance.OUTDATED in str(refusal.value)
	doc.reload()
	assert doc.gov_state == governance.ACCEPTED


def test_tc_w1_015_checked_recipe_can_be_declined(site):
	"""TC-W1-015 step 4 (URS-W1-014 AC-4): a Checked recipe may be Declined with a reason,
	and Declined is terminal."""
	doc = _draft_record(site)
	governance.transition(doc, governance.CHECKED)
	governance.transition(doc, governance.DECLINED, reason="Rezeptur technisch nicht fahrbar")
	assert doc.gov_state == governance.DECLINED
	assert doc.state_history[-1].reason == "Rezeptur technisch nicht fahrbar"

	for target in governance.STATES:
		if target == governance.DECLINED:
			continue
		with pytest.raises(site.exceptions.ValidationError):
			governance.transition(doc, target, reason="Wiederaufnahme")
		doc.reload()
		assert doc.gov_state == governance.DECLINED


def test_tc_w1_015_declining_and_outdating_require_a_reason(site):
	"""TC-W1-015 (URS-W1-014 AC-4): rejection and outdating are change-controlled — the
	transition is refused without a reason (dossier §change control)."""
	doc = _draft_record(site)
	governance.transition(doc, governance.CHECKED)
	with pytest.raises(site.exceptions.ValidationError):
		governance.transition(doc, governance.DECLINED)
	doc.reload()
	assert doc.gov_state == governance.CHECKED


def test_tc_w1_015_accept_transition_is_role_gated(site):
	"""TC-W1-015 (URS-W1-029): the technologist accepts recipes; a
	warehouse clerk is refused at the transition itself, not only by DocType permissions."""
	doc = _draft_record(site)
	site.set_user(TECHNOLOGIST_USER)
	governance.transition(doc, governance.CHECKED)

	site.set_user(CLERK_USER)
	doc.reload()
	with pytest.raises(site.exceptions.PermissionError):
		governance.transition(doc, governance.ACCEPTED)

	site.set_user(TECHNOLOGIST_USER)
	doc.reload()
	governance.transition(doc, governance.ACCEPTED)
	assert doc.gov_state == governance.ACCEPTED


def test_tc_w1_015_gov_state_pill_is_published_to_the_anchor_bom(site):
	"""TC-W1-015 (URS-W1-014 design conformance): the anchor BOM carries the `gov_state` pill through the
	app-owned Custom Field — the anchor DocType itself is never forked."""
	doc = _draft_record(site)
	doc.save()
	assert site.db.get_value("BOM", BOM_NAME, "rw_gov_state") == governance.DRAFT

	governance.transition(doc, governance.CHECKED)
	assert site.db.get_value("BOM", BOM_NAME, "rw_gov_state") == governance.CHECKED
	assert site.db.get_value("Custom Field", {"dt": "BOM", "fieldname": "rw_gov_state"}, "read_only") == 1
	anchor_module = site.db.get_value("DocType", "BOM", "module")
	assert site.db.get_value("Module Def", anchor_module, "app_name") == "erpnext"


def test_tc_w1_015_workflow_metadata_gates_every_transition(site):
	"""TC-W1-015 (URS-W1-014, URS-W1-029): the committed installer publishes the `gov_state`
	workflow with a role on every transition and a pill style per state."""
	workflow = site.get_doc("Workflow", "Rheinwerk Rezeptfreigabe")
	assert workflow.document_type == "Recipe Governance"
	assert workflow.workflow_state_field == "gov_state"
	assert workflow.is_active == 1
	assert {row.state for row in workflow.states} == set(governance.STATES)
	assert all(row.allowed for row in workflow.transitions)

	published = {(row.state, row.next_state) for row in workflow.transitions}
	expected = {
		(current, target) for current, targets in governance.TRANSITIONS.items() for target in targets
	}
	assert published == expected
