"""W1-4 — in-use lock for recipes referenced by active production orders.

TC-W1-018 (URS-W1-017): while PO-2026-0001 is active, BOM-RW-CHM-0003-001 can neither be
modified nor outdated nor declined; once the order is Completed the outdating succeeds
through an accepted successor.

Qcadoo baseline: `TechnologyService.java:159-172` (`isTechnologyUsedInActiveOrder`) and
`TechnologyValidationAspect.java:135-141` (in-use check on Outdated/Declined).
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
pytest.importorskip("frappe")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")

BOM_NAME = "BOM-RW-CHM-0003-001"
ROUTING = "RT-COMPOUND-01"
ORDER = "PO-2026-0001"


#: Anchor status ↔ `exec_state` pairs a real order carries; the lock reads `exec_state`
#: where the extension is installed and falls back to the anchor status otherwise.
ACTIVE = ("In Process", "In Progress")
PENDING = ("Not Started", "Pending")
DONE = ("Completed", "Completed")


def _set_order_state(site, states: tuple[str, str]) -> None:
	"""Put PO-2026-0001 into an anchor status and its `exec_state` reflection.

	Written directly rather than through the state machine: this suite is about the lock, not
	about transition legality, and the fixture order would otherwise need a full journey.
	"""
	status, exec_state = states
	values = {"status": status}
	if site.get_meta("Work Order").get_field("exec_state"):
		values["exec_state"] = exec_state
	site.db.set_value("Work Order", ORDER, values, update_modified=False)


def _governance(site):
	return site.get_doc("Recipe Governance", governance.governance_name(BOM_NAME))


def test_tc_w1_018_active_order_locks_the_recipe(site):
	"""TC-W1-018 step 1 (URS-W1-017 AC-1): an in-progress PO-2026-0001 marks the accepted
	recipe as locked and lists the locking order on the governance record."""
	_set_order_state(site, ACTIVE)
	assert governance.active_orders_for_recipe(BOM_NAME) == [ORDER]

	doc = _governance(site)
	doc.save()
	assert doc.in_use_lock == 1
	assert ORDER in doc.in_use_orders


def test_tc_w1_018_a_pending_order_does_not_lock_the_recipe(site):
	"""URS-W1-017 — the lock covers Accepted/In Progress/Interrupted only.

	A submitted but still Pending order carries the anchor status `Not Started`, which must
	not be read as active: the technologist may still retire the recipe
	(`docs/design/W1-recipe-governance.md` §6).
	"""
	_set_order_state(site, PENDING)
	assert governance.active_orders_for_recipe(BOM_NAME) == []

	doc = _governance(site)
	doc.save()
	assert doc.in_use_lock == 0


@pytest.mark.parametrize("states", [("Not Started", governance.ACCEPTED), ACTIVE])
def test_tc_w1_018_outdating_is_refused_while_an_order_is_active(site, states):
	"""TC-W1-018 step 1 (URS-W1-017 AC-2): outdating an accepted recipe used by an active
	order is refused, and the refusal names the order."""
	_set_order_state(site, states)
	doc = _governance(site)

	with pytest.raises(site.exceptions.ValidationError) as refusal:
		governance.transition(doc, governance.OUTDATED, reason="Rezeptur ersetzt")
	assert ORDER in str(refusal.value)

	doc.reload()
	assert doc.gov_state == governance.ACCEPTED


def test_tc_w1_018_declining_is_refused_while_an_order_is_active(site):
	"""TC-W1-018 step 1 (URS-W1-017 AC-2): declining a recipe used by an active order is
	refused as well — the lock covers every state change that would retire the recipe."""
	_set_order_state(site, ACTIVE)
	site.db.set_value(
		"Recipe Governance", governance.governance_name(BOM_NAME), "gov_state", governance.CHECKED
	)
	doc = _governance(site)

	with pytest.raises(site.exceptions.ValidationError) as refusal:
		governance.transition(doc, governance.DECLINED, reason="Rezeptur zurückgezogen")
	assert ORDER in str(refusal.value)

	doc.reload()
	assert doc.gov_state == governance.CHECKED


def test_tc_w1_018_modification_is_refused_while_an_order_is_active(site):
	"""TC-W1-018 step 1 (URS-W1-017 AC-1): a locked recipe cannot be modified either — the
	anchor BOM refuses the change while an active order references it."""
	_set_order_state(site, ACTIVE)
	site.db.set_value(
		"Recipe Governance", governance.governance_name(BOM_NAME), "gov_state", governance.DRAFT
	)

	bom = site.get_doc("BOM", BOM_NAME)
	with pytest.raises(site.exceptions.ValidationError) as refusal:
		bom.cancel()
	assert ORDER in str(refusal.value)
	assert site.db.get_value("BOM", BOM_NAME, "docstatus") == 1


def test_tc_w1_018_accepting_a_successor_is_refused_while_the_predecessor_is_in_use(site):
	"""TC-W1-018 step 1 (URS-W1-017 AC-2, URS-W1-016 AC-2): accepting a successor would
	outdate the locked predecessor, so it is refused while the order is active."""
	_set_order_state(site, ACTIVE)
	successor = site.copy_doc(site.get_doc("BOM", BOM_NAME))
	successor.is_default = 0
	successor.is_active = 1
	successor.insert()
	doc = site.get_doc({"doctype": "Recipe Governance", "bom": successor.name, "routing": ROUTING}).insert()
	governance.transition(doc, governance.CHECKED)

	with pytest.raises(site.exceptions.ValidationError) as refusal:
		governance.transition(doc, governance.ACCEPTED)
	assert ORDER in str(refusal.value)
	assert governance.gov_state(BOM_NAME) == governance.ACCEPTED


def test_tc_w1_018_completed_order_releases_the_lock(site):
	"""TC-W1-018 step 2 (URS-W1-017 AC-2): once PO-2026-0001 is Completed the lock is gone —
	the successor is accepted and the predecessor moves to Outdated."""
	_set_order_state(site, DONE)
	assert governance.active_orders_for_recipe(BOM_NAME) == []

	successor = site.copy_doc(site.get_doc("BOM", BOM_NAME))
	successor.is_default = 0
	successor.is_active = 1
	successor.insert()
	doc = site.get_doc({"doctype": "Recipe Governance", "bom": successor.name, "routing": ROUTING}).insert()
	governance.transition(doc, governance.CHECKED)
	governance.transition(doc, governance.ACCEPTED)

	assert governance.gov_state(successor.name) == governance.ACCEPTED
	assert governance.gov_state(BOM_NAME) == governance.OUTDATED
	assert _governance(site).in_use_lock == 0
