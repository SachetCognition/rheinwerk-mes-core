"""TC-W2-018 / TC-W2-019 — template instantiation and automatic result (W2-4).

Verifies **URS-W2-013 AC-1…3**: the ERPNext `Quality Inspection` engine is adopted, not
forked — QIT-COMPOUND instantiates its three parameters with limits, a passing reading set
auto-accepts, and an out-of-limit reading auto-rejects while naming the failing parameter
and the limit it violates.
"""

from __future__ import annotations

import pytest
from test_w2_quality_support import (
	BATCH_C1,
	COMPOUND_ITEM,
	DENSITY,
	FAILING_READINGS,
	MOISTURE,
	PASSING_READINGS,
	TEMPLATE,
	VISCOSITY,
	inspection_for,
	require_fixture,
	require_quality_schema,
	set_qa_state,
)

pytest.importorskip("frappe")
inspections = pytest.importorskip("rheinwerk_mes.quality.inspections")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")


@pytest.fixture
def quality_site(site):
	require_quality_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	set_qa_state(site, BATCH_C1, qa_state.QUARANTINED)
	return site


def test_template_instantiates_three_parameters_with_their_limits(quality_site):
	"""URS-W2-013 AC-1 / TC-W2-018 step 1 — QIT-COMPOUND instantiated on the inspection."""
	doc = inspection_for(quality_site, BATCH_C1)

	assert doc.quality_inspection_template == TEMPLATE
	assert doc.item_code == COMPOUND_ITEM and doc.batch_no == BATCH_C1
	limits = {row.specification: (row.min_value, row.max_value) for row in doc.readings}
	assert limits == {
		VISCOSITY: (1200.0, 1400.0),
		DENSITY: (1.02, 1.06),
		MOISTURE: (0.0, 0.5),
	}


def test_template_carries_the_unit_of_every_parameter(quality_site):
	"""URS-W2-013 AC-1 — units travel with the parameter so the queue can suffix them."""
	rows = inspections.reading_rows(inspection_for(quality_site, BATCH_C1))

	assert {row["parameter"]: row["unit"] for row in rows} == {
		VISCOSITY: "mPa·s",
		DENSITY: "g/cm³",
		MOISTURE: "%",
	}


def test_inspection_type_vocabulary_is_the_anchor_vocabulary(quality_site):
	"""URS-W2-013 AC-1 — Incoming / Outgoing / In Process are adopted, not redefined."""
	options = quality_site.get_meta("Quality Inspection").get_field("inspection_type").options
	assert set(inspections.INSPECTION_TYPES) <= set(options.split("\n"))


def test_readings_inside_the_limits_accept_the_inspection_automatically(quality_site):
	"""URS-W2-013 AC-2 / TC-W2-018 step 2 — 1290 mPa·s, 1,04 g/cm³, 0,3 % all pass."""
	doc = inspection_for(quality_site, BATCH_C1, PASSING_READINGS)

	assert doc.status == inspections.ACCEPTED
	assert {row.status for row in doc.readings} == {inspections.ACCEPTED}


def test_out_of_limit_reading_rejects_and_identifies_the_failing_parameter(quality_site):
	"""URS-W2-013 AC-3 / TC-W2-019 — 1450 mPa·s rejects, naming parameter and limit."""
	doc = inspection_for(quality_site, BATCH_C1, FAILING_READINGS)

	assert doc.status == inspections.REJECTED
	failing = inspections.failing_readings(doc)
	assert [row["parameter"] for row in failing] == [VISCOSITY]
	assert inspections.limit_text(failing[0]) == "1200 – 1400 mPa·s"


def test_readings_are_recorded_in_the_german_number_format(quality_site):
	"""URS-W2-013 AC-2 — a decimal reading is stored as 1,04, not 1.04 (i18n rule)."""
	doc = inspection_for(quality_site, BATCH_C1, PASSING_READINGS)

	density = next(row for row in doc.readings if row.specification == DENSITY)
	assert density.reading_1 == "1,04"


def test_batch_without_a_template_is_refused_naming_the_item(quality_site):
	"""URS-W2-013 AC-1 — an item with no template cannot be inspected by accident."""
	quality_site.db.set_value("Item", COMPOUND_ITEM, "quality_inspection_template", None)

	with pytest.raises(Exception) as refusal:
		inspection_for(quality_site, BATCH_C1)
	assert COMPOUND_ITEM in str(refusal.value)


def test_anchor_quality_inspection_doctype_is_not_forked(quality_site, repo_root):
	"""URS-W2-013 — every extension is a Custom Field owned by `rheinwerk_mes`."""
	assert not (repo_root / "rheinwerk_mes" / "quality" / "doctype" / "quality_inspection").exists()
	owners = {
		field: quality_site.db.get_value(
			"Custom Field", {"dt": "Quality Inspection", "fieldname": field}, "name"
		)
		for field in ("rw_work_order", "rw_disposition")
	}
	assert all(owners.values()), owners
