"""Shared helpers for the W1-1 `exec_state` acceptance suites (URS-W1-001…004).

Not a test module in itself — it holds the fixture helpers the
`test_w1_exec_state_*.py` suites share (the W1-1 file footprint keeps every W1-1
artefact inside `tests/acceptance/test_w1_exec_state_*.py`, so `conftest.py` stays
untouched for the parallel wave children).
"""

from __future__ import annotations

from typing import Any

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"
OPERATOR_USER = "o.weber@rheinwerk-chemie.example"


def require_fixture(site: Any, name: str) -> Any:
	"""Return the seeded production order, skipping when the site was not seeded."""
	import pytest

	if not site.db.exists("Work Order", name):
		pytest.skip(f"programme fixture {name} not seeded on this site")
	return site.get_doc("Work Order", name)


def draft_order(site: Any, name: str = FIRST_ORDER) -> Any:
	"""The seeded order in docstatus 0 and `exec_state` Pending."""
	doc = require_fixture(site, name)
	if doc.docstatus != 0:
		import pytest

		pytest.skip(f"{name} is already submitted on this site")
	reset_state(site, doc)
	return doc


def submitted_order(site: Any, name: str = FIRST_ORDER) -> Any:
	"""The seeded order submitted (anchor docstatus 1) and back in Pending."""
	doc = require_fixture(site, name)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	doc.reload()
	reset_state(site, doc)
	return doc


def reset_state(site: Any, doc: Any, state: str = "Pending") -> Any:
	"""Force `exec_state` (bypassing the machine) so a test starts from a known state."""
	site.db.set_value("Work Order", doc.name, "exec_state", state, update_modified=False)
	site.db.delete("Order State History", {"parent": doc.name})
	doc.reload()
	return doc


def force_state(site: Any, doc: Any, state: str) -> Any:
	"""Alias of `reset_state` that reads better when arranging an arbitrary state."""
	return reset_state(site, doc, state)


def test_support_module_exposes_helpers():
	"""Guard so this module keeps its documented helper surface for the W1-1 suites."""
	assert callable(draft_order) and callable(submitted_order) and callable(force_state)
