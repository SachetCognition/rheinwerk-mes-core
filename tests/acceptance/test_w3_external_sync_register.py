"""TC-W3-023 — external-sync register completeness and contract coverage.

Verifies **URS-W3-019**: every entry of the published register carries system, plant,
direction, data objects, evidence of use and a disposition; dossier open question §8.2 #6 is
marked answered; and every sync dispositioned *carry* is reflected in a committed contract
fixture that actually exists.

Offline test — the register is code plus a published document, no site needed.
"""

from __future__ import annotations

from pathlib import Path

from rheinwerk_mes.integration.boundary import external_sync_register as register
from rheinwerk_mes.integration.boundary import schema

EVIDENCE = Path("docs/evidence/W3-external-sync-register.md")


def _document(repo_root: Path) -> str:
	return (repo_root / EVIDENCE).read_text(encoding="utf-8")


def test_tc_w3_023_step_1_every_register_entry_is_complete(repo_root):
	"""TC-W3-023 step 1 (URS-W3-019 AC-1): no entry is incomplete — each names system,
	plant, direction, data objects, evidence of use, disposition and rationale."""
	assert register.incomplete_entries() == ()
	assert len(register.REGISTER) >= 12

	ids = [entry["id"] for entry in register.REGISTER]
	assert len(ids) == len(set(ids))
	for entry in register.REGISTER:
		assert entry["disposition"] in register.DISPOSITIONS
		assert entry["direction"] in {"inbound", "outbound", "outbound (lesend)"} or entry[
			"direction"
		].startswith("bidirektional")
		assert entry["evidence_paths"]


def test_tc_w3_023_step_1_qcadoo_external_number_consumers_are_all_registered():
	"""TC-W3-023 step 1 (URS-W3-019 AC-1): the survey covers every carrier of Qcadoo's
	`externalNumber`/`externalSynchronized` pair (`OrderFields.java:48,88`) — order,
	masterOrder, delivery, technology, product, company/address, location,
	assignmentToShift, batch/trackingRecord — plus the read-only REST API and the
	transactional-e-mail plugin."""
	paths = " ".join(str(entry["evidence_paths"]) for entry in register.REGISTER)
	assert "OrderFields.java:48,88" in paths
	for carrier in (
		"MasterOrderFields",
		"DeliveryFields",
		"TechnologyFields",
		"ProductFields",
		"CompanyFields",
		"AddressFields",
		"LocationFields",
		"AssignmentToShiftFields",
		"BatchModelHelper",
		"TechnologyApiController",
		"emailNotifications",
	):
		assert carrier in paths, carrier


def test_tc_w3_023_step_1_plant_c_erpnext_integrations_are_all_registered():
	"""TC-W3-023 step 1 (URS-W3-019 AC-1): every ERPNext integration the Plant C substrate
	ships is registered with evidence that it is unconfigured (confirmed unused)."""
	plant_c = [entry for entry in register.REGISTER if "C" in entry["plant"]]
	paths = " ".join(str(entry["evidence_paths"]) for entry in plant_c)
	for capability in ("plaid_settings", "edi/doctype/code_list", "telephony", "stock_controller"):
		assert capability in paths, capability
	unused = [entry for entry in plant_c if entry["in_use"].startswith("bestätigt ungenutzt")]
	assert len(unused) >= 4


def test_tc_w3_023_step_1_open_question_82_6_is_answered(repo_root):
	"""TC-W3-023 step 1 (URS-W3-019 AC-1): dossier open question §8.2 #6 is marked answered,
	with the finding that no external WMS and no live external ERP interface exists."""
	assert register.ANSWER_82_6.startswith("Answered")
	assert "no external WMS" in register.ANSWER_82_6

	document = _document(repo_root)
	assert "§8.2 #6" in document
	assert "beantwortet" in document
	assert "kein externes WMS" in document


def test_tc_w3_023_step_2_every_carried_sync_has_a_contract_fixture():
	"""TC-W3-023 step 2 (URS-W3-019 AC-2): each *carry* entry names at least one contract
	v1.0 fixture, and every named fixture exists and parses."""
	carried = register.carried_fixtures()
	assert carried, "no carried sync in the register"
	available = set(schema.fixture_names())
	for entry_id, fixtures in carried.items():
		assert fixtures, entry_id
		for name in fixtures:
			assert name in available, f"{entry_id} names a missing fixture {name}"
			assert schema.fixture(name)["contract_version"] == "1.0"


def test_tc_w3_023_the_published_document_matches_the_register(repo_root):
	"""TC-W3-023 (URS-W3-019): the published evidence embeds the generated register
	verbatim, so document and code cannot drift."""
	document = _document(repo_root)
	assert register.BEGIN_MARKER in document
	assert register.END_MARKER in document
	generated = register.render_markdown()
	block = document.split(register.BEGIN_MARKER)[1].split(register.END_MARKER)[0]
	assert generated.strip() == block.strip()
