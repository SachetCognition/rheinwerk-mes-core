"""W2-7 — hazmat profile lifecycle (URS-W2-023).

TC-W2-031: a hazmat profile (UN number / SDS reference / Lagerklasse) is maintained as
app-owned master data, resolves onto a batch through its item with a batch-level override for
repacked goods, refuses a batch of a hazmat-mandatory item that has no profile, and
version-audits every change of a regulatory field with user, timestamp and before/after.

White space in all three legacy systems (dossier §6.3) — there is no parity contract; the
rules asserted here come from the URS, TRGS 510 and CLP (see `docs/design/W2-hazmat.md`).
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
contracts = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.contracts")
profiles = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.profiles")

ITEM = "RW-CHM-0001"
BATCH = "BATCH-A-0001"
PROFILE = "HAZ-RW-CHM-0001"


def _require_profile(site) -> str:
	if not site.db.exists("Hazmat Profile", PROFILE):
		pytest.skip("hazmat fixture not seeded on this site")
	return PROFILE


def test_un_number_is_normalised_and_shapes_are_enforced(site):
	"""URS-W2-023: the UN number is a four-digit ADR identifier, rendered `UN NNNN`.

	Vocabulary contract — the Lagerklasse list is TRGS 510's and CLP statement codes must
	match their regulated shape, so unusable regulatory data cannot be saved at all. Runs
	site-backed because the refusals are German-first via `frappe._()`.
	"""
	assert contracts.normalise_un_number("1866") == "UN 1866"
	assert contracts.normalise_un_number("un1866") == "UN 1866"
	assert contracts.normalise_un_number("UN 1866") == "UN 1866"
	for invalid in ("", "UN 186", "UN 18660", "ADR 1866"):
		with pytest.raises(contracts.HazmatDataError):
			contracts.normalise_un_number(invalid)

	assert contracts.validate_storage_class("4.1a") == "4.1A"
	with pytest.raises(contracts.HazmatDataError):
		contracts.validate_storage_class("9")

	assert contracts.validate_statement_code("h226", contracts.STATEMENT_HAZARD) == "H226"
	assert contracts.validate_statement_code("euh014", contracts.STATEMENT_HAZARD) == "EUH014"
	assert contracts.validate_statement_code("p210", contracts.STATEMENT_PRECAUTIONARY) == "P210"
	with pytest.raises(contracts.HazmatDataError):
		contracts.validate_statement_code("P210", contracts.STATEMENT_HAZARD)


def test_tc_w2_031_profile_is_visible_on_the_batch_via_its_item(site):
	"""TC-W2-031 step 1 (URS-W2-023 AC-1): the profile UN 1866 / SDS-RW-0001 / Lagerklasse 3
	linked to RW-CHM-0001 resolves onto BATCH-A-0001 through the item."""
	_require_profile(site)

	resolved = profiles.effective_profile(batch=BATCH)
	assert resolved is not None
	assert resolved["un_number"] == "UN 1866"
	assert resolved["sds_reference"] == "SDS-RW-0001"
	assert resolved["storage_class"] == "3"
	# The Lagerklasse is never shown as a bare code (German-first, TRGS 510 designation).
	assert profiles.batch_chip(BATCH)["storage_class_label"] == ("Lagerklasse 3 — Entzündbare Flüssigkeiten")


def test_tc_w2_031_batch_level_override_wins_for_repacked_goods(site):
	"""TC-W2-031 step 1 (URS-W2-023 AC-1): a batch may override the item profile — the case
	of re-drummed or repacked goods — and the override is what every surface resolves."""
	_require_profile(site)
	override = frappe.get_doc(
		{
			"doctype": "Hazmat Profile",
			"profile_name": "HAZ-TEST-UMGEPACKT",
			"un_number": "1263",
			"storage_class": "3",
			"sds_reference": "SDS-RW-9001",
		}
	).insert(ignore_permissions=True)

	batch = frappe.get_doc("Batch", BATCH)
	batch.set(profiles.BATCH_PROFILE_FIELD, override.name)
	batch.save(ignore_permissions=True)

	assert profiles.effective_profile_name(batch=BATCH) == override.name
	assert profiles.effective_profile(batch=BATCH)["un_number"] == "UN 1263"
	# The read-only mirrors that make hazmat a column follow the override (URS-W2-024).
	assert frappe.db.get_value("Batch", BATCH, profiles.BATCH_UN_NUMBER_FIELD) == "UN 1263"


def test_tc_w2_031_batch_of_a_hazmat_mandatory_item_without_profile_is_refused(site):
	"""TC-W2-031 step 2 (URS-W2-023 AC-2): a hazmat-mandatory item without a linked profile
	refuses batch creation, and the refusal names rule, record and resolution."""
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": "RW-TEST-HAZMAT-PFLICHT",
			"item_name": "Testgefahrstoff ohne Profil",
			"item_group": "Raw Material",
			"stock_uom": "Kg",
			"has_batch_no": 1,
			profiles.ITEM_MANDATORY_FIELD: 1,
		}
	).insert(ignore_permissions=True)

	with pytest.raises(frappe.ValidationError) as refusal:
		frappe.get_doc({"doctype": "Batch", "batch_id": "BATCH-TEST-0001", "item": item.name}).insert(
			ignore_permissions=True
		)

	message = str(refusal.value)
	assert item.name in message
	assert "Gefahrstoffprofil" in message

	# With a profile linked, the same batch saves — the gate is the missing profile, nothing else.
	frappe.db.set_value("Item", item.name, profiles.ITEM_PROFILE_FIELD, PROFILE, update_modified=False)
	batch = frappe.get_doc({"doctype": "Batch", "batch_id": "BATCH-TEST-0001", "item": item.name}).insert(
		ignore_permissions=True
	)
	assert batch.get(profiles.BATCH_STORAGE_CLASS_FIELD) == "3"


def test_tc_w2_031_sds_reference_change_is_version_audited(site):
	"""TC-W2-031 step 3 (URS-W2-023 AC-3): updating the SDS reference bumps the profile
	revision and records field, before/after value, user and timestamp."""
	name = _require_profile(site)
	profile = frappe.get_doc("Hazmat Profile", name)
	revision_before = profile.revision
	previous_reference = profile.sds_reference

	profile.sds_reference = "SDS-RW-0001-A"
	profile.save(ignore_permissions=True)

	assert profile.revision == revision_before + 1
	audited = [row for row in profile.revisions if row.changed_field == "sds_reference"]
	assert audited, [row.changed_field for row in profile.revisions]
	latest = audited[-1]
	assert latest.value_before == previous_reference
	assert latest.value_after == "SDS-RW-0001-A"
	assert latest.changed_by == frappe.session.user
	assert latest.changed_on


def test_tc_w2_031_anchors_are_not_forked(site):
	"""URS-W2-023 (programme rule 1): every hazmat extension of `Item`/`Batch` is a Custom
	Field owned by the `Regulatory Hazmat` module — the anchor DocTypes stay standard."""
	for doctype, fieldnames in (
		("Item", (profiles.ITEM_PROFILE_FIELD, profiles.ITEM_MANDATORY_FIELD)),
		(
			"Batch",
			(
				profiles.BATCH_PROFILE_FIELD,
				profiles.BATCH_UN_NUMBER_FIELD,
				profiles.BATCH_STORAGE_CLASS_FIELD,
			),
		),
	):
		assert not frappe.db.get_value("DocType", doctype, "custom")
		for fieldname in fieldnames:
			custom_field = frappe.db.get_value(
				"Custom Field", {"dt": doctype, "fieldname": fieldname}, ["module"], as_dict=True
			)
			assert custom_field, f"{doctype}.{fieldname} must be a Custom Field"
			assert custom_field.module == "Regulatory Hazmat"
			# The field must not exist on the anchor DocType itself (that would be a fork).
			assert not frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname})
