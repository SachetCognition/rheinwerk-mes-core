"""TC-W2-024 / TC-W2-025 — Certificate of Analysis generation and immutability (W2-5).

Verifies **URS-W2-017 AC-1…3**: a CoA is generated from the Accepted inspection of a
released batch — snapshotting readings, limits, batch/item identity, signatory and issue
date, with a PDF attached — it is refused for a batch without an accepted inspection, its
snapshot survives amendment or cancellation of the source inspection, and a new version
supersedes the prior certificate while both remain retrievable.
"""

from __future__ import annotations

import pytest
from test_w2_quality_support import (
	BATCH_C1,
	BATCH_C2,
	COMPOUND_ITEM,
	DENSITY,
	FIRST_ORDER,
	MOISTURE,
	VISCOSITY,
	accepted_inspection_for,
	require_fixture,
	require_quality_schema,
	set_qa_state,
)

pytest.importorskip("frappe")
coa = pytest.importorskip("rheinwerk_mes.quality.coa")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")


@pytest.fixture
def released_batch(site):
	require_quality_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	inspection = accepted_inspection_for(site, BATCH_C1, work_order=FIRST_ORDER)
	assert site.db.get_value("Batch", BATCH_C1, "qa_state") == qa_state.RELEASED
	return inspection


def test_certificate_snapshots_the_accepted_readings_with_their_limits(released_batch, site):
	"""URS-W2-017 AC-1 / TC-W2-024 step 1 — three readings with limits and units."""
	cert = coa.issue(BATCH_C1, attach_pdf=False)

	snapshot = {row.parameter: (row.reading, row.limit_text) for row in cert.readings}
	assert snapshot == {
		VISCOSITY: ("1290", "1200 – 1400 mPa·s"),
		DENSITY: ("1,04", "1,02 – 1,06 g/cm³"),
		MOISTURE: ("0,3", "0 – 0,5 %"),
	}


def test_certificate_carries_batch_item_signatory_and_issue_date(released_batch, site):
	"""URS-W2-017 AC-1 / TC-W2-024 step 1 — identity of the certified material."""
	cert = coa.issue(BATCH_C1, attach_pdf=False)

	assert (cert.batch, cert.item) == (BATCH_C1, COMPOUND_ITEM)
	assert cert.quality_inspection == released_batch.name
	assert cert.signatory == site.session.user
	assert cert.issue_date and cert.certificate_status == "Issued"
	assert coa.view_model(cert.name)["issue_date"] == coa._german_date(cert.issue_date)


def test_certificate_attaches_a_rendered_pdf(released_batch):
	"""URS-W2-017 AC-1 / TC-W2-024 step 1 — the PDF is attached, not generated ad hoc."""
	cert = coa.issue(BATCH_C1)

	assert cert.pdf_document and cert.pdf_document.endswith(".pdf")


def test_certificate_for_a_batch_without_an_accepted_inspection_is_refused(site):
	"""URS-W2-017 AC-2 / TC-W2-024 step 2 — refusal names the missing inspection."""
	require_quality_schema(site)
	require_fixture(site, "Batch", BATCH_C2)
	set_qa_state(site, BATCH_C2, qa_state.QUARANTINED)

	with pytest.raises(Exception) as refusal:
		coa.issue(BATCH_C2)
	assert "Qualitätsprüfung" in str(refusal.value) and BATCH_C2 in str(refusal.value)


def test_snapshot_survives_cancellation_of_the_source_inspection(released_batch, site):
	"""URS-W2-017 AC-3 / TC-W2-025 step 1 — the certificate is not a live view."""
	cert = coa.issue(BATCH_C1, attach_pdf=False)
	before = [(row.parameter, row.reading, row.reading_result) for row in cert.readings]

	inspection = site.get_doc("Quality Inspection", released_batch.name)
	inspection.flags.ignore_permissions = True
	inspection.cancel()

	cert.reload()
	assert [(row.parameter, row.reading, row.reading_result) for row in cert.readings] == before


def test_editing_an_issued_certificate_is_refused(released_batch, site):
	"""URS-W2-017 AC-3 — immutability is enforced, not merely documented."""
	cert = coa.issue(BATCH_C1, attach_pdf=False)

	cert.signatory = "Administrator"
	cert.issue_date = "2026-01-01"
	with pytest.raises(Exception) as refusal:
		cert.save()
	assert "unveränderlich" in str(refusal.value)


def test_new_version_supersedes_the_prior_certificate_and_both_remain_retrievable(released_batch):
	"""URS-W2-017 AC-3 / TC-W2-025 step 2 — versioning instead of editing."""
	first = coa.issue(BATCH_C1, attach_pdf=False)
	second = coa.issue(BATCH_C1, attach_pdf=False)

	first.reload()
	assert (first.certificate_status, first.superseded_by) == ("Superseded", second.name)
	assert (second.version, second.supersedes) == (first.version + 1, first.name)
	retrieved = coa.certificates_for_batch(BATCH_C1)
	assert [row["name"] for row in retrieved][:2] == [second.name, first.name]
	assert retrieved[1]["status_label"] == "Ersetzt"
