"""TC-W2-026 / TC-W2-027 — Trace Ribbon in the CoA and business retrieval (W2-5).

Verifies **URS-W2-018 AC-1** (the certificate embeds the same ribbon model the standalone
Trace Ribbon renders, print-safe with icon + label rather than colour alone) and
**URS-W2-019 AC-1** (B. Vogel finds a certificate by batch, item or number and opens it
read-only with the PDF downloadable).
"""

from __future__ import annotations

import pytest
from test_w2_quality_support import (
	BATCH_C1,
	COMPOUND_ITEM,
	FIRST_ORDER,
	accepted_inspection_for,
	require_fixture,
	require_quality_schema,
)

pytest.importorskip("frappe")
coa = pytest.importorskip("rheinwerk_mes.quality.coa")
ribbon = pytest.importorskip("rheinwerk_mes.genealogy.ribbon")

BUSINESS_VIEWER = "b.vogel@rheinwerk-chemie.example"


@pytest.fixture
def certificate(site):
	require_quality_schema(site)
	require_fixture(site, "Batch", BATCH_C1)
	accepted_inspection_for(site, BATCH_C1, work_order=FIRST_ORDER)
	return coa.issue(BATCH_C1)


def test_embedded_ribbon_matches_the_standalone_ribbon(certificate):
	"""URS-W2-018 AC-1 / TC-W2-026 — identical node and state set at the same instant."""
	embedded = coa.view_model(certificate.name)["ribbon"]
	standalone = ribbon.ribbon(BATCH_C1)

	def nodes(model):
		chips = [*model["left"], model["focus"], *model["right"]]
		return [(chip["batch"], tuple(pill["label"] for pill in chip["pills"])) for chip in chips]

	assert nodes(embedded) == nodes(standalone)


def test_certificate_html_renders_the_ribbon_print_safe(certificate):
	"""URS-W2-018 AC-1 / TC-W2-026 — printed status is icon + label, never colour alone."""
	html = coa.render_html(certificate.name)

	assert BATCH_C1 in html and "Chargen-Trace" in html
	assert "Analysenzertifikat" in html
	# Every reading row prints a glyph and the German result label next to it.
	assert "✓" in html and "Angenommen" in html


def test_certificate_renders_dates_and_mass_in_the_estate_conventions(certificate):
	"""URS-W2-018 AC-1 — DD.MM.YYYY and kg, as required by the design skill."""
	model = coa.view_model(certificate.name)

	assert model["issue_date"].count(".") == 2 and len(model["issue_date"]) == 10
	assert model["qty"].endswith(" kg")


def test_business_viewer_finds_the_certificate_by_batch_item_and_number(certificate, site):
	"""URS-W2-019 AC-1 / TC-W2-027 — the Command-Dashboard search finds the CoA."""
	for term in (BATCH_C1, COMPOUND_ITEM, certificate.name):
		found = [row["name"] for row in coa.search(term)]
		assert certificate.name in found, term
	assert coa.search("")[:1] == []


def test_business_viewer_opens_the_certificate_read_only_with_the_pdf(certificate, site):
	"""URS-W2-019 AC-1 / TC-W2-027 — read-only, no state-changing affordance, PDF there."""
	if not site.db.exists("User", BUSINESS_VIEWER):
		pytest.skip("persona B. Vogel not seeded on this site")
	site.set_user(BUSINESS_VIEWER)
	try:
		model = coa.view_model(certificate.name)
		assert model["pdf_document"]
		assert site.has_permission("CoA Certificate", "read", certificate.name)
		assert not site.has_permission("CoA Certificate", "write", certificate.name)
		assert [row["writable"] for row in coa.search(BATCH_C1)] == [False]
	finally:
		site.set_user("Administrator")
