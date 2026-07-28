"""W0 naming/numbering scheme.

TC-W0-017 (URS-W0-014) — the recorded series are applied estate-wide and legacy
Qcadoo trigger numbers stay queryable in `legacy_refs`. Decision: ADR-011.
"""

from __future__ import annotations

import re

# Formats pinned by ADR-011; the app registry lives in `rheinwerk_mes.setup.naming` and
# is read through the connected site, because the offline CI job has no Frappe.
NAMING = "rheinwerk_mes.setup.naming"
WORK_ORDER_SERIES = "PO-.YYYY.-.####."
BATCH_SERIES = "BATCH-.{plant}.-.####."
HANDLING_UNIT_SERIES = "HU-.####."

DECISION_NOTE = "docs/adr/ADR-011-naming-numbering.md"
ORDER = "PO-2026-0001"


def test_tc_w0_017_decision_note_records_every_series(repo_root):
	"""TC-W0-017 step 1 (URS-W0-014 AC-1): the naming decision note exists and records
	the batch, production-order and handling-unit formats."""
	note = (repo_root / DECISION_NOTE).read_text(encoding="utf-8")
	for series in (WORK_ORDER_SERIES, BATCH_SERIES, HANDLING_UNIT_SERIES):
		assert series in note


def test_tc_w0_017_registered_series_render_the_fixture_identifiers(site):
	"""TC-W0-017 step 1 (URS-W0-014 AC-1): the registry covers batch, production order
	and handling unit, and renders exactly the identifiers the URS/TST fixtures name."""
	registry = site.get_attr(f"{NAMING}.SERIES")
	assert registry == {
		"Work Order": WORK_ORDER_SERIES,
		"Batch": BATCH_SERIES,
		"Handling Unit": HANDLING_UNIT_SERIES,
	}
	preview = site.get_attr(f"{NAMING}.preview")
	assert preview(BATCH_SERIES, {"plant": "A"}, counter=1) == "BATCH-A-0001"
	assert preview(HANDLING_UNIT_SERIES, {}, counter=1) == "HU-0001"
	assert re.fullmatch(r"PO-\d{4}-0001", preview(WORK_ORDER_SERIES, {}, counter=1))


def test_tc_w0_017_production_order_series_is_applied(site):
	"""TC-W0-017 step 1 (URS-W0-014 AC-1): the anchor `Work Order` names from
	`PO-.YYYY.-.####.` and the seeded order matches the decided format."""
	assert site.get_attr(f"{NAMING}.is_applicable")("Work Order", WORK_ORDER_SERIES)
	naming_series = site.get_meta("Work Order").get_field("naming_series")
	assert naming_series.default == WORK_ORDER_SERIES
	assert naming_series.options.splitlines()[0] == WORK_ORDER_SERIES
	assert re.fullmatch(r"PO-\d{4}-\d{4}", ORDER)
	assert site.db.exists("Work Order", ORDER)


def test_tc_w0_017_legacy_trigger_number_stays_queryable(site):
	"""TC-W0-017 step 2 (URS-W0-014 AC-2): the Qcadoo trigger number 000123/2025 of the
	migrated Plant A order is preserved in `legacy_refs` and searchable."""
	refs = site.get_doc("Work Order", ORDER).legacy_refs
	assert [(row.source_system, row.source_identifier) for row in refs] == [("Qcadoo", "000123/2025")]
	assert site.get_all(
		"Legacy Ref",
		filters={"source_identifier": "000123/2025", "parenttype": "Work Order"},
		pluck="parent",
	) == [ORDER]
