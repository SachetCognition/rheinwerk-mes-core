"""TC-W3-016 — contract fixture suite and version discipline.

Verifies **URS-W3-013**: the frozen v1.0 contract has a machine-validated schema per message
type; the committed fixture suite holds at least one happy, one duplicate and one rejection
fixture per message type (≥ 9 fixtures) and every fixture behaves as its manifest declares;
and a backward-incompatible schema change is detected as requiring a version increment, with
both versions validating during the transition window.

Offline test — this is the CI contract job (`.github/workflows/ci.yml`, job `contracts`); it
needs no site, which is what lets it run on every push.
"""

from __future__ import annotations

import json

import pytest

from rheinwerk_mes.integration.boundary import contracts, schema

MANIFEST = "manifest.json"


def manifest() -> list[dict]:
	path = schema.FIXTURE_ROOT / MANIFEST
	return json.loads(path.read_text(encoding="utf-8"))["fixtures"]


def fixtures_of(case: str, message_type: str) -> list[dict]:
	return [entry for entry in manifest() if entry["case"] == case and entry["message_type"] == message_type]


def test_tc_w3_016_step_1_contract_v1_0_is_frozen_and_machine_validated():
	"""TC-W3-016 step 1 (URS-W3-013 AC-1): the frozen version is 1.0 and each of the three
	ADR-002 message types has a committed, loadable JSON-Schema document."""
	assert contracts.CONTRACT_VERSION == "1.0"
	assert schema.versions() == ("1.0",)
	for message_type in contracts.MESSAGE_TYPES:
		definition = schema.schema(message_type)
		assert definition["type"] == "object"
		assert definition["properties"]["message_type"]["const"] == message_type
		assert definition["properties"]["contract_version"]["const"] == "1.0"
		assert definition["additionalProperties"] is False


def test_tc_w3_016_step_1_the_fixture_suite_covers_every_case_per_message_type():
	"""TC-W3-016 step 1 (URS-W3-013 AC-3): ≥ 9 fixtures — at least one happy, one duplicate
	and one rejection fixture for each of the three message types."""
	names = set(schema.fixture_names()) - {MANIFEST}
	assert len(names) >= 9
	assert {entry["fixture"] for entry in manifest()} == names

	for message_type in contracts.MESSAGE_TYPES:
		for case in ("happy", "duplicate", "rejection"):
			assert fixtures_of(case, message_type), f"{message_type}/{case}"


@pytest.mark.parametrize("entry", manifest(), ids=lambda entry: entry["fixture"])
def test_tc_w3_016_step_1_every_fixture_validates_as_its_manifest_declares(entry):
	"""TC-W3-016 step 1 (URS-W3-013 AC-1/AC-3): each committed fixture is schema-valid, or —
	for the declared rejection cases — refused by the machine validation with the
	CONTRACT_VIOLATION reason code."""
	payload = schema.fixture(entry["fixture"])
	assert payload["message_type"] == entry["message_type"]
	assert payload["contract_version"] == contracts.CONTRACT_VERSION

	if entry["schema_valid"]:
		assert schema.validate_message(payload) is payload
	else:
		with pytest.raises(schema.SchemaViolation) as refused:
			schema.validate_message(payload)
		assert refused.value.reason_code == contracts.REASON_CONTRACT_VIOLATION
		assert refused.value.path


def test_tc_w3_016_step_1_duplicate_fixtures_repeat_their_happy_path_identity():
	"""TC-W3-016 step 1 (URS-W3-013 AC-3): a duplicate fixture is a redelivery — same message
	id as its happy counterpart, so idempotency is exercised, not a second message."""
	for entry in manifest():
		if entry["case"] != "duplicate":
			continue
		duplicate = schema.fixture(entry["fixture"])
		happy = [schema.fixture(other["fixture"]) for other in fixtures_of("happy", entry["message_type"])]
		assert duplicate["message_id"] in {payload["message_id"] for payload in happy}


def test_tc_w3_016_step_1_rejection_reasons_are_machine_readable():
	"""TC-W3-016 step 1 (URS-W3-010 AC-3): every declared rejection reason is one of the
	contract's stable reason codes, not free text."""
	for entry in manifest():
		if entry["reason_code"] is None:
			assert entry["case"] == "happy"
			continue
		assert entry["reason_code"] in contracts.REASON_CODES


def test_tc_w3_016_step_2_a_backward_incompatible_change_requires_a_new_version():
	"""TC-W3-016 step 2 (URS-W3-013 AC-2): a new required property, a removed property, a
	narrowed enum and a changed type are each detected as needing a version increment, while
	an added optional property is not."""
	old = schema.schema(contracts.ORDERS_IN)

	new_required = json.loads(json.dumps(old))
	new_required["required"].append("external_order_kind")
	assert schema.requires_version_increment(old, new_required)

	removed = json.loads(json.dumps(old))
	del removed["properties"]["external_order_kind"]
	assert schema.requires_version_increment(old, removed)

	narrowed = json.loads(json.dumps(old))
	narrowed["properties"]["external_order_kind"]["enum"] = ["sales-order"]
	assert schema.requires_version_increment(old, narrowed)

	retyped = json.loads(json.dumps(old))
	retyped["properties"]["demand"]["properties"]["quantity"]["type"] = "string"
	assert schema.requires_version_increment(old, retyped)

	additive = json.loads(json.dumps(old))
	additive["properties"]["priority"] = {"type": "string"}
	assert not schema.requires_version_increment(old, additive)
	assert schema.incompatibilities(old, additive) == ()


def test_tc_w3_016_step_2_both_versions_validate_during_a_transition_window(tmp_path):
	"""TC-W3-016 step 2 (URS-W3-013 AC-2): with a v1.1 directory present, `versions()` serves
	both, a v1.0 message keeps validating against v1.0 and a v1.1 message validates against
	the incremented schema — the transition window the AC requires."""
	v1_1 = schema.CONTRACT_ROOT / "v1.1"
	definition = json.loads(json.dumps(schema.schema(contracts.ORDERS_IN)))
	definition["properties"]["contract_version"]["const"] = "1.1"
	definition["required"].append("external_order_kind")
	v1_1.mkdir()
	try:
		(v1_1 / schema.SCHEMA_FILENAMES[contracts.ORDERS_IN]).write_text(
			json.dumps(definition), encoding="utf-8"
		)
		assert schema.versions() == ("1.0", "1.1")

		legacy = schema.fixture("erp-in-001-happy.json")
		assert schema.validate_message(legacy) is legacy

		migrated = {**legacy, "contract_version": "1.1"}
		assert schema.validate_message(migrated) is migrated

		incomplete = {key: value for key, value in migrated.items() if key != "external_order_kind"}
		with pytest.raises(schema.SchemaViolation):
			schema.validate_message(incomplete)
	finally:
		for child in v1_1.iterdir():
			child.unlink()
		v1_1.rmdir()
		schema.schema.cache_clear()
