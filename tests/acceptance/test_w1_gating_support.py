"""Shared helpers for the W1-2 / W1-3 gating acceptance suites (URS-W1-005…013, -033).

Not a test module in itself — it holds the arrangement helpers the
`test_w1_gating_*.py` suites share, so `tests/conftest.py` stays untouched for the
parallel wave children (same convention as the W1-1 suites).
"""

from __future__ import annotations

from typing import Any

import pytest

COMPANY = "Rheinwerk Chemie GmbH"
FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
RECIPE = "BOM-RW-CHM-0003-001"
RM_WAREHOUSE = "RM Lager Nord - RWC"
EXPIRED_BATCH = "BATCH-A-0002"
COMPONENT_A = "RW-CHM-0001"
COMPONENT_B = "RW-CHM-0002"
LINE = "LINE-1"


def require_fixture(site: Any, doctype: str, name: str) -> Any:
	"""Return a seeded programme fixture, skipping when the site was not seeded."""
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def submitted_order(site: Any, name: str = FIRST_ORDER, state: str = "Pending") -> Any:
	"""The seeded order submitted (anchor docstatus 1) and forced into `state`."""
	doc = require_fixture(site, "Work Order", name)
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	doc.reload()
	return force_state(site, doc, state)


def force_state(site: Any, doc: Any, state: str) -> Any:
	"""Force `exec_state` (bypassing the machine) so a test starts from a known state."""
	site.db.set_value("Work Order", doc.name, "exec_state", state, update_modified=False)
	site.db.delete("Order State History", {"parent": doc.name})
	site.db.delete("Execution Gate Log", {"reference_name": doc.name})
	doc.reload()
	return doc


def set_fields(site: Any, doc: Any, **values: Any) -> Any:
	"""Arrange anchor fields directly in the DB (arrangement only, never the act)."""
	for fieldname, value in values.items():
		site.db.set_value("Work Order", doc.name, fieldname, value, update_modified=False)
	doc.reload()
	return doc


def set_governance_state(site: Any, recipe: str, state: str) -> None:
	"""Arrange a recipe's `gov_state` directly (the governance module owns the transitions)."""
	name = site.db.get_value("Recipe Governance", {"bom": recipe}, "name")
	if not name:
		pytest.skip(f"recipe governance for {recipe} not seeded on this site")
	site.db.set_value("Recipe Governance", name, "gov_state", state, update_modified=False)


def stock_ledger_count(site: Any) -> int:
	"""Number of Stock Ledger Entries on the site — a side-effect probe for hard stops."""
	return site.db.count("Stock Ledger Entry")


def test_support_module_exposes_helpers():
	"""Guard so this module keeps its documented helper surface for the W1-2/W1-3 suites."""
	assert callable(submitted_order) and callable(force_state) and callable(set_governance_state)
