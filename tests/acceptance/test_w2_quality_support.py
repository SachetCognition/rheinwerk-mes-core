"""Shared arrangement helpers for the W2-4/W2-5 acceptance suites (URS-W2-013…019).

Not a test module in itself: the `test_w2_quality_*` and `test_w2_coa_*` suites share these
helpers so `tests/conftest.py` stays untouched for the parallel wave children (same
convention as `test_w1_gating_support.py`).
"""

from __future__ import annotations

from typing import Any

import pytest

COMPANY = "Rheinwerk Chemie GmbH"
COMPOUND_ITEM = "RW-CHM-0003"
TEMPLATE = "QIT-COMPOUND"

BATCH_C1 = "BATCH-C-1001"
BATCH_C2 = "BATCH-C-1002"
BATCH_A2 = "BATCH-A-0002"
FIRST_ORDER = "PO-2026-0001"

VISCOSITY = "Viskosität"
DENSITY = "Dichte"
MOISTURE = "Feuchte"

#: The passing reading set of TC-W2-018 step 2.
PASSING_READINGS: dict[str, float] = {VISCOSITY: 1290, DENSITY: 1.04, MOISTURE: 0.3}
#: Viscosity out of limit — TC-W2-019.
FAILING_READINGS: dict[str, float] = {VISCOSITY: 1450, DENSITY: 1.04, MOISTURE: 0.3}


def require_fixture(site: Any, doctype: str, name: str) -> Any:
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def require_quality_schema(site: Any) -> None:
	"""Skip when `rheinwerk_mes.setup.w2_quality` has not run on this site."""
	if not site.get_meta("Quality Inspection").get_field("rw_work_order"):
		pytest.skip("W2 quality custom fields not installed on this site")
	if not site.db.exists("Quality Inspection Template", TEMPLATE):
		pytest.skip(f"inspection template {TEMPLATE} not seeded on this site")


def set_qa_state(site: Any, batch: str, state: str) -> None:
	"""Arrange a batch's `qa_state` directly — the genealogy child owns the transitions."""
	site.db.set_value("Batch", batch, "qa_state", state, update_modified=False)


def inspection_for(
	site: Any,
	batch: str,
	readings: dict[str, float] | None = None,
	submit: bool = False,
	work_order: str | None = None,
) -> Any:
	"""A fresh inspection for `batch`, optionally with readings entered and submitted."""
	from rheinwerk_mes.quality import inspections

	doc = inspections.create_inspection(batch, work_order=work_order)
	if readings is not None:
		doc = inspections.enter_readings(doc.name, readings, submit=submit)
	return doc


def accepted_inspection_for(site: Any, batch: str, work_order: str | None = None) -> Any:
	"""A submitted, Accepted inspection — the precondition of every CoA case."""
	from rheinwerk_mes.genealogy import qa_state

	set_qa_state(site, batch, qa_state.QUARANTINED)
	return inspection_for(site, batch, PASSING_READINGS, submit=True, work_order=work_order)


def test_support_module_exposes_helpers():
	"""Guard so this module keeps its documented helper surface for the W2-4/W2-5 suites."""
	assert callable(inspection_for) and callable(accepted_inspection_for)
