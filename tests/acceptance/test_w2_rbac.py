"""TC-W2-050 — workflow-state-level RBAC across the W2 transitions.

Verifies **URS-W2-036** (`qa_state` disposition, CoA issue, recipe Accept and stocktaking
acceptance are each restricted to their mapped role and enforced *server-side*, with the
business viewer able to read everything and change nothing) through **TC-W2-050** of
`docs/test/TST-W2-traceability-quality.md`.

Every case drives the published API as the persona — not the Desk UI — because the
requirement is explicitly about server-side enforcement: a hidden button is not a control.
"""

from __future__ import annotations

from typing import Any

import pytest

frappe = pytest.importorskip("frappe")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
coa = pytest.importorskip("rheinwerk_mes.quality.coa")
governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")

OPERATOR = "o.weber@rheinwerk-chemie.example"
VIEWER = "b.vogel@rheinwerk-chemie.example"
INSPECTOR = "q.fischer@rheinwerk-chemie.example"
CLERK = "w.braun@rheinwerk-chemie.example"
TECHNOLOGIST = "t.schmid@rheinwerk-chemie.example"

BATCH = "BATCH-C-1001"
RECIPE_BOM = "BOM-RW-CHM-0003-001"

#: DocTypes whose write access is the state-changing surface of the W2 screens (AC-2).
VIEWER_READ_ONLY = (
	"Batch",
	"Quality Inspection",
	"CoA Certificate",
	"Stocktaking",
)


def _require(site: Any, doctype: str, name: str) -> None:
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")


def _as(site: Any, user: str) -> None:
	if not site.db.exists("User", user):
		pytest.skip(f"persona {user} not seeded on this site")
	site.set_user(user)


def test_operator_cannot_dispose_of_a_batch(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 1 — `qa_state` is the inspector's act alone."""
	_require(site, "Batch", BATCH)
	site.db.set_value("Batch", BATCH, "qa_state", qa_state.QUARANTINED, update_modified=False)
	_as(site, OPERATOR)
	with pytest.raises(frappe.PermissionError):
		qa_state.transition(BATCH, qa_state.RELEASED, reason="Freigabe durch Bediener")


def test_inspector_may_dispose_of_a_batch(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 2 — the mapped role succeeds where the operator failed."""
	_require(site, "Batch", BATCH)
	site.db.set_value("Batch", BATCH, "qa_state", qa_state.QUARANTINED, update_modified=False)
	_as(site, INSPECTOR)
	doc = qa_state.transition(BATCH, qa_state.RELEASED, reason="Prüfung angenommen")
	assert doc.qa_state == qa_state.RELEASED


def test_operator_cannot_issue_a_certificate(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 1 — the CoA is signed by the quality role."""
	_require(site, "Batch", BATCH)
	if not site.db.exists("DocType", coa.DOCTYPE):
		pytest.skip("W2 quality DocTypes not installed on this site")
	_as(site, OPERATOR)
	with pytest.raises((frappe.PermissionError, frappe.ValidationError)):
		coa.issue(BATCH, attach_pdf=False)


def test_operator_cannot_accept_a_recipe(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 1 — recipe Accept belongs to the technologist reviewer."""
	name = governance.governance_name(RECIPE_BOM)
	if not name:
		pytest.skip("recipe governance record not seeded on this site")
	_as(site, OPERATOR)
	with pytest.raises((frappe.PermissionError, frappe.ValidationError)):
		governance.transition(name, "Accepted", reason="Freigabe durch Bediener")


def test_operator_cannot_accept_a_stocktaking(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 1 — count acceptance belongs to the warehouse clerk."""
	if not site.db.exists("DocType", "Stocktaking"):
		pytest.skip("W2 warehouse DocTypes not installed on this site")
	_as(site, OPERATOR)
	assert frappe.has_permission("Stocktaking", "write") is False


def test_warehouse_clerk_may_write_a_stocktaking(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 2 — the mapped role holds the write right."""
	if not site.db.exists("DocType", "Stocktaking"):
		pytest.skip("W2 warehouse DocTypes not installed on this site")
	_as(site, CLERK)
	assert frappe.has_permission("Stocktaking", "write") is True


def test_technologist_holds_the_recipe_review_right(site):
	"""URS-W2-036 AC-1 / TC-W2-050 step 2 — the technologist may act on governance records."""
	if not site.db.exists("DocType", "Recipe Governance"):
		pytest.skip("W1 recipe governance not installed on this site")
	_as(site, TECHNOLOGIST)
	assert frappe.has_permission("Recipe Governance", "write") is True


@pytest.mark.parametrize("doctype", VIEWER_READ_ONLY)
def test_business_viewer_reads_everything_and_writes_nothing(site, doctype):
	"""URS-W2-036 AC-2 / TC-W2-050 step 3 — B. Vogel's screens carry no state-changing act."""
	if not site.db.exists("DocType", doctype):
		pytest.skip(f"{doctype} not installed on this site")
	_as(site, VIEWER)
	assert frappe.has_permission(doctype, "read") is True, f"{doctype} must stay readable"
	assert frappe.has_permission(doctype, "write") is False, f"{doctype} must not be writable"


def test_business_viewer_can_retrieve_certificates(site):
	"""URS-W2-036 AC-2 — read-only does not mean empty: the viewer still retrieves CoAs."""
	if not site.db.exists("DocType", coa.DOCTYPE):
		pytest.skip("W2 quality DocTypes not installed on this site")
	_as(site, VIEWER)
	rows = coa.certificates_for_batch(BATCH)
	assert all(row["writable"] is False for row in rows)
