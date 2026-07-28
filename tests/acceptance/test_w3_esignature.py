"""URS-W2-029 AC-2 (enforced in W3) — electronic signatures on the four dispositive acts.

Covers `docs/design/W3-esignature-enforcement.md`: the append-only `Electronic Signature`
record, re-authentication, single-use freshness, the payload hash, the gates on QA release /
QA block / CoA issue / recipe acceptance, the "signed where performed" rule for an inspection
that releases its own batch, and the absence of a signature demand on operational acts.

Every test arms enforcement itself (`Rheinwerk Compliance Settings.esignature_enforced`), which
ships off — see §4 of the design note.
"""

from __future__ import annotations

from typing import Any

import pytest
from test_w2_genealogy_support import BATCH_A2, require_fixture, require_w2_schema, set_state

frappe = pytest.importorskip("frappe")
esignature = pytest.importorskip("rheinwerk_mes.compliance.esignature")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
audit = pytest.importorskip("rheinwerk_mes.execution_gating.audit")

SIGNER = "esig.tester@rheinwerk-chemie.example"
PASSWORD = "Unterschrift-Test-2026!"
INSPECTOR_ROLES = ("Quality Manager", "Rheinwerk Technologist", "Rheinwerk Warehouse Clerk")


@pytest.fixture
def armed(site):
	"""Enforcement on for the duration of one test (rolled back with the transaction)."""
	require_w2_schema(site)
	site.db.set_single_value(esignature.SETTINGS_DOCTYPE, "esignature_enforced", 1)
	yield site
	site.set_user("Administrator")


@pytest.fixture
def signer(site):
	"""A user with a password this suite knows, so signing can be exercised for real."""
	from frappe.utils.password import update_password

	if not site.db.exists("User", SIGNER):
		user = site.get_doc(
			{
				"doctype": "User",
				"email": SIGNER,
				"first_name": "Elke",
				"last_name": "Signatur",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	else:
		user = site.get_doc("User", SIGNER)
	existing = {row.role for row in user.get("roles") or []}
	for role in INSPECTOR_ROLES:
		if site.db.exists("Role", role) and role not in existing:
			user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	update_password(SIGNER, PASSWORD)
	site.set_user(SIGNER)
	yield SIGNER
	site.set_user("Administrator")


@pytest.fixture
def batch(armed, signer):
	require_fixture(armed, "Batch", BATCH_A2)
	set_state(armed, BATCH_A2, qa_state.QUARANTINED)
	armed.db.delete("Batch QA State History", {"parent": BATCH_A2})
	return BATCH_A2


def sign(batch: str, act: str = esignature.ACT_QA_RELEASE, **kwargs: Any) -> str:
	return esignature.sign(
		document_type="Batch",
		document_name=batch,
		act=act,
		password=PASSWORD,
		reason=kwargs.pop("reason", "Freigabe nach Prüfung"),
		**kwargs,
	)


# ------------------------------------------------------------------ the signature itself


def test_signature_records_signer_meaning_and_payload_hash(batch):
	"""AC-2 — the record captures who declared what, when, over which payload."""
	name = sign(batch)

	doc = frappe.get_doc(esignature.DOCTYPE, name)
	assert doc.signer == SIGNER and doc.signer_full_name == "Elke Signatur"
	assert doc.meaning == "Freigegeben" and doc.act == esignature.ACT_QA_RELEASE
	assert (doc.document_type, doc.document_name) == ("Batch", batch)
	assert doc.signed_at and doc.payload_hash and not doc.consumed_by
	assert doc.payload_hash == esignature.payload_hash(
		esignature.signed_payload(frappe.get_doc("Batch", batch), esignature.ACT_QA_RELEASE)
	)


def test_wrong_password_produces_no_signature(batch):
	"""AC-2 — re-authentication is the point; a failed one leaves no record behind."""
	before = frappe.db.count(esignature.DOCTYPE)
	with pytest.raises(frappe.AuthenticationError):
		esignature.sign(
			document_type="Batch",
			document_name=batch,
			act=esignature.ACT_QA_RELEASE,
			password="falsches-kennwort",
			reason="Freigabe",
		)
	assert frappe.db.count(esignature.DOCTYPE) == before


def test_release_and_block_signatures_need_a_reason(batch):
	"""DEC-W2-029 — a block and its reversal are never signed without a stated reason."""
	for act in (esignature.ACT_QA_RELEASE, esignature.ACT_QA_BLOCK):
		with pytest.raises(frappe.ValidationError) as refusal:
			sign(batch, act=act, reason="   ")
		assert "Begründung" in str(refusal.value)


def test_signature_is_immutable_and_undeletable(batch):
	"""AC-2 — the evidence can be superseded, never corrected or removed."""
	doc = frappe.get_doc(esignature.DOCTYPE, sign(batch))

	doc.reason = "nachträglich geändert"
	with pytest.raises(frappe.ValidationError) as edit_refusal:
		doc.save(ignore_permissions=True)
	assert "unveränderlich" in str(edit_refusal.value)

	fresh = frappe.get_doc(esignature.DOCTYPE, doc.name)
	with pytest.raises(frappe.ValidationError) as delete_refusal:
		fresh.delete(ignore_permissions=True)
	assert "nicht gelöscht" in str(delete_refusal.value)


def test_no_role_may_write_a_signature(armed):
	"""AC-2 — signatures exist only via the signing API; no role can author them."""
	for perm in frappe.get_all(
		"Custom DocPerm",
		filters={"parent": esignature.DOCTYPE},
		fields=["role", "write", "create", "delete"],
	):
		assert not (perm["write"] or perm["create"] or perm["delete"]), perm["role"]


# --------------------------------------------------------------------------- the QA gate


def test_release_is_refused_without_a_signature(batch):
	"""AC-2 — the refusal names rule, record and resolution."""
	with pytest.raises(frappe.ValidationError) as refusal:
		qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe nach Prüfung")
	message = str(refusal.value)
	assert esignature.SIGNATURE_RULE in message and batch in message
	assert "unterzeichnen" in message
	assert frappe.db.get_value("Batch", batch, "qa_state") == qa_state.QUARANTINED


def test_signed_release_passes_and_consumes_the_signature(batch):
	"""AC-2 — one signature, one act: spending it stamps it."""
	name = sign(batch)

	qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe nach Prüfung")

	assert frappe.db.get_value("Batch", batch, "qa_state") == qa_state.RELEASED
	consumed = frappe.db.get_value(esignature.DOCTYPE, name, ["consumed_by", "consumed_at"], as_dict=True)
	assert consumed["consumed_by"] == "qa_state:Quarantined->Released" and consumed["consumed_at"]


def test_a_signature_cannot_be_replayed_on_a_second_act(batch):
	"""AC-2 — a spent signature is not a licence for the next transition."""
	sign(batch)
	qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe nach Prüfung")

	with pytest.raises(frappe.ValidationError):
		qa_state.transition(batch, qa_state.BLOCKED, reason="Nachträglich gesperrt")
	assert frappe.db.get_value("Batch", batch, "qa_state") == qa_state.RELEASED


def test_an_expired_signature_does_not_satisfy_the_gate(batch):
	"""D2 — freshness is part of the control, not a convenience."""
	from frappe.utils import add_to_date, now_datetime

	name = sign(batch)
	frappe.db.set_value(
		esignature.DOCTYPE,
		name,
		"signed_at",
		add_to_date(now_datetime(), seconds=-(esignature.FRESHNESS_SECONDS + 60)),
		update_modified=False,
	)

	with pytest.raises(frappe.ValidationError):
		qa_state.transition(batch, qa_state.RELEASED, reason="Freigabe nach Prüfung")


def test_entering_quarantine_is_never_signed(armed, signer):
	"""DEC-W2-029 — only release and block are dispositive; entry is not."""
	require_fixture(armed, "Batch", BATCH_A2)
	set_state(armed, BATCH_A2, qa_state.BLOCKED)
	armed.set_user("Administrator")
	doc = armed.get_doc("Batch", BATCH_A2)
	assert esignature.pending("Batch", BATCH_A2, esignature.ACT_QA_RELEASE) is None
	assert doc.qa_state == qa_state.BLOCKED


def test_signature_is_audited_as_a_gate_entry(batch):
	"""AC-2 — the audit trail shows the signature independently of the record."""
	name = sign(batch)

	entries = [
		entry for entry in audit.entries_for("Batch", batch) if entry["gate"] == esignature.SIGNATURE_GATE
	]
	assert entries and name in entries[-1]["detail"]
	assert entries[-1]["rule"] == esignature.SIGNATURE_RULE


# -------------------------------------------------- CoA issue and recipe acceptance


@pytest.fixture
def accepted_inspection(site, signer):
	"""An accepted inspection of a released batch, arranged *before* enforcement is armed."""
	from test_w2_quality_support import BATCH_C1, FIRST_ORDER, accepted_inspection_for
	from test_w2_quality_support import require_fixture as require_quality_fixture

	site.set_user("Administrator")
	site.db.set_single_value(esignature.SETTINGS_DOCTYPE, "esignature_enforced", 0)
	require_quality_fixture(site, "Batch", BATCH_C1)
	inspection = accepted_inspection_for(site, BATCH_C1, work_order=FIRST_ORDER)
	site.db.set_single_value(esignature.SETTINGS_DOCTYPE, "esignature_enforced", 1)
	site.set_user(SIGNER)
	return inspection


def test_certificate_issue_is_refused_unsigned_and_permitted_signed(accepted_inspection):
	"""AC-2 — the certificate leaves the estate only with a named certifier."""
	coa = pytest.importorskip("rheinwerk_mes.quality.coa")
	batch = accepted_inspection.get("batch_no")

	with pytest.raises(frappe.ValidationError) as refusal:
		coa.issue(batch, attach_pdf=False)
	assert esignature.SIGNATURE_RULE in str(refusal.value)

	esignature.sign(
		document_type="Quality Inspection",
		document_name=accepted_inspection.name,
		act=esignature.ACT_COA_ISSUE,
		password=PASSWORD,
	)
	certificate = coa.issue(batch, attach_pdf=False)
	assert certificate.batch == batch


def test_batch_report_lists_signatures_per_batch_and_per_certificate(accepted_inspection):
	"""DEC-W2-029 — one audit list per batch, spanning inspection and certificate."""
	coa = pytest.importorskip("rheinwerk_mes.quality.coa")
	batch = accepted_inspection.get("batch_no")
	esignature.sign(
		document_type="Quality Inspection",
		document_name=accepted_inspection.name,
		act=esignature.ACT_COA_ISSUE,
		password=PASSWORD,
	)
	coa.issue(batch, attach_pdf=False)
	sign(batch, act=esignature.ACT_QA_BLOCK, reason="Kundenreklamation")

	report = esignature.batch_report(batch)

	assert [row["act"] for row in report] == [esignature.ACT_COA_ISSUE, esignature.ACT_QA_BLOCK]
	assert {row["signer"] for row in report} == {SIGNER}


def test_inspection_signature_covers_the_release_it_triggers(armed, signer):
	"""D3 — one act, one signature: signed where the inspector performs it."""
	from test_w2_quality_support import BATCH_C2, PASSING_READINGS, inspection_for, set_qa_state
	from test_w2_quality_support import require_fixture as require_quality_fixture

	inspections = pytest.importorskip("rheinwerk_mes.quality.inspections")
	armed.set_user("Administrator")
	require_quality_fixture(armed, "Batch", BATCH_C2)
	set_qa_state(armed, BATCH_C2, qa_state.QUARANTINED)
	inspection = inspection_for(armed, BATCH_C2)
	armed.set_user(SIGNER)
	esignature.sign(
		document_type="Quality Inspection",
		document_name=inspection.name,
		act=esignature.ACT_QA_RELEASE,
		password=PASSWORD,
		reason="Prüfung angenommen",
	)

	submitted = inspections.enter_readings(inspection.name, PASSING_READINGS, submit=True)

	assert submitted.status == "Accepted"
	assert armed.db.get_value("Batch", BATCH_C2, "qa_state") == qa_state.RELEASED


def test_recipe_acceptance_is_refused_unsigned_and_permitted_signed(armed, signer):
	"""AC-2 — accepting a recipe authorises every batch made to it."""
	governance = pytest.importorskip("rheinwerk_mes.recipe_isa88.governance")
	bom = "BOM-RW-CHM-0003-001"
	name = governance.governance_name(bom)
	if not name:
		pytest.skip("recipe governance fixture not seeded on this site")
	armed.db.set_value("Recipe Governance", name, "gov_state", governance.CHECKED)

	with pytest.raises(frappe.ValidationError) as refusal:
		governance.transition(name, governance.ACCEPTED, reason="Freigabe")
	assert esignature.SIGNATURE_RULE in str(refusal.value)

	esignature.sign(
		document_type="Recipe Governance",
		document_name=name,
		act=esignature.ACT_RECIPE_ACCEPT,
		password=PASSWORD,
	)
	governance.transition(name, governance.ACCEPTED, reason="Freigabe")
	assert armed.db.get_value("Recipe Governance", name, "gov_state") == governance.ACCEPTED


# ------------------------------------------------------- enforcement switch (design §4)


def test_unsigned_release_passes_while_enforcement_is_off(site, signer):
	"""§4 — the switch ships off so the estate's automated release paths keep working."""
	require_w2_schema(site)
	site.db.set_single_value(esignature.SETTINGS_DOCTYPE, "esignature_enforced", 0)
	require_fixture(site, "Batch", BATCH_A2)
	set_state(site, BATCH_A2, qa_state.QUARANTINED)

	qa_state.transition(BATCH_A2, qa_state.RELEASED, reason="Freigabe nach Prüfung")

	assert site.db.get_value("Batch", BATCH_A2, "qa_state") == qa_state.RELEASED
