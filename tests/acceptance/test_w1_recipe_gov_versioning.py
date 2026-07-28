"""W1-4 — immutability of Accepted recipes and successor versioning.

TC-W1-017 (URS-W1-016): editing an accepted recipe is refused; a change goes through a new
anchor BOM version whose governance record starts in Draft, and accepting the successor
moves the predecessor to Outdated.
"""

from __future__ import annotations

import pytest

from rheinwerk_mes.recipe_isa88 import governance

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"


def _successor(site, quantity: float = 90.0) -> str:
	"""A second anchor BOM version for the compound with a changed component quantity."""
	successor = site.copy_doc(site.get_doc("BOM", BOM_NAME))
	successor.is_default = 0
	successor.is_active = 1
	next(row for row in successor.items if row.item_code == "RW-CHM-0001").qty = quantity
	successor.insert()
	return successor.name


def test_tc_w1_017_accepted_recipe_lines_cannot_be_edited(site):
	"""TC-W1-017 step 1 (URS-W1-016 AC-1): changing a component line of the accepted
	BOM-RW-CHM-0003-001 is refused and the stored quantity is unchanged.

	The anchor's own submit lock refuses the field edit first; the governance-aware refusal
	is asserted on the cancel route below, which the anchor does allow.
	"""
	assert governance.gov_state(BOM_NAME) == governance.ACCEPTED
	bom = site.get_doc("BOM", BOM_NAME)
	next(row for row in bom.items if row.item_code == "RW-CHM-0001").qty = 75.0

	with pytest.raises(site.exceptions.ValidationError):
		bom.save()

	assert site.db.get_value("BOM Item", {"parent": BOM_NAME, "item_code": "RW-CHM-0001"}, "qty") == 80.0


def test_tc_w1_017_accepted_recipe_cannot_be_reworked_by_cancelling(site):
	"""TC-W1-017 step 1 (URS-W1-016 AC-1): cancelling an accepted BOM to rewrite it is
	refused by the governance hook, which names the state and the versioning route."""
	bom = site.get_doc("BOM", BOM_NAME)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		bom.cancel()
	message = str(refusal.value)
	assert BOM_NAME in message
	assert "unveränderlich" in message
	assert site.db.get_value("BOM", BOM_NAME, "docstatus") == 1


def test_tc_w1_017_unaccepted_recipe_stays_reworkable(site):
	"""TC-W1-017 step 1 (URS-W1-016 AC-1): the lock is bound to the Accepted state — a
	recipe still in Draft may be cancelled and reworked."""
	site.db.set_value(
		"Recipe Governance", governance.governance_name(BOM_NAME), "gov_state", governance.DRAFT
	)
	bom = site.get_doc("BOM", BOM_NAME)
	bom.cancel()
	assert bom.docstatus == 2


def test_tc_w1_017_successor_version_starts_in_draft(site):
	"""TC-W1-017 step 2 (URS-W1-016 AC-2): the change lands as a new anchor BOM version
	(anchor versioned naming, never a fork) whose governance record starts in Draft."""
	successor = _successor(site)
	assert successor == "BOM-RW-CHM-0003-002"

	doc = site.get_doc({"doctype": "Recipe Governance", "bom": successor, "routing": ROUTING}).insert()
	assert doc.gov_state == governance.DRAFT
	assert governance.gov_state(BOM_NAME) == governance.ACCEPTED


def test_tc_w1_017_accepting_successor_outdates_predecessor(site):
	"""TC-W1-017 step 3 (URS-W1-016 AC-2): accepting the successor moves the
	predecessor to Outdated, and the predecessor's history records why."""
	successor = _successor(site)
	doc = site.get_doc({"doctype": "Recipe Governance", "bom": successor, "routing": ROUTING}).insert()
	governance.transition(doc, governance.CHECKED)
	governance.transition(doc, governance.ACCEPTED)

	assert governance.gov_state(successor) == governance.ACCEPTED
	assert governance.gov_state(BOM_NAME) == governance.OUTDATED
	assert site.db.get_value("BOM", BOM_NAME, "rw_gov_state") == governance.OUTDATED

	predecessor = site.get_doc("Recipe Governance", governance.governance_name(BOM_NAME))
	assert predecessor.state_history[-1].to_state == governance.OUTDATED
	assert successor in predecessor.state_history[-1].reason


def test_tc_w1_017_outdated_recipe_is_terminal_and_not_reusable(site):
	"""TC-W1-017 step 3 (URS-W1-016 AC-2): Outdated is terminal — the predecessor can never
	be revived, and `is_accepted` no longer answers True for it."""
	successor = _successor(site)
	doc = site.get_doc({"doctype": "Recipe Governance", "bom": successor, "routing": ROUTING}).insert()
	governance.transition(doc, governance.CHECKED)
	governance.transition(doc, governance.ACCEPTED)

	predecessor = site.get_doc("Recipe Governance", governance.governance_name(BOM_NAME))
	assert governance.is_accepted(BOM_NAME) is False
	for target in (governance.DRAFT, governance.CHECKED, governance.ACCEPTED, governance.DECLINED):
		with pytest.raises(site.exceptions.ValidationError):
			governance.transition(predecessor, target, reason="Reaktivierung")
		predecessor.reload()
		assert predecessor.gov_state == governance.OUTDATED
