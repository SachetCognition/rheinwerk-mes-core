"""W0 audit trail on canonical master data.

TC-W0-018 (URS-W0-015) — every create/update/delete of a canonical master-data
entity is recorded with user, timestamp and changed fields, and is retrievable per
record through `rheinwerk_mes.manufacturing_core.audit.get_audit_trail`.

The repo-structure checks run offline (no site); the behavioural checks request the
`site` fixture and are skipped where no Frappe site is available.
"""

from __future__ import annotations

import ast
import json

import pytest

TECHNOLOGIST = "t.schmid@rheinwerk-chemie.example"
CANONICAL = ("Item", "Workstation", "BOM", "Work Order")
AUDIT_SETUP = "rheinwerk_mes.setup.audit.setup_audit_trail"
RENAMED = "Prüfharz Audit (Rev. B)"


def _module_constant(path, name):
	tree = ast.parse(path.read_text(encoding="utf-8"))
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and any(
			isinstance(target, ast.Name) and target.id == name for target in node.targets
		):
			return ast.literal_eval(node.value)
	raise AssertionError(f"{name} not assigned in {path}")


def test_tc_w0_018_canonical_anchors_are_audited(repo_root):
	"""URS-W0-015: the audited set covers every canonical master-data entity."""
	audited = _module_constant(repo_root / "rheinwerk_mes/setup/property_setters.py", "AUDITED_DOCTYPES")
	assert set(CANONICAL) <= set(audited)


def test_tc_w0_018_audit_setup_is_committed_code(repo_root):
	"""URS-W0-015: versioning is asserted by hooks on install and migration, never by hand."""
	hooks = repo_root / "rheinwerk_mes/hooks.py"
	assert _module_constant(hooks, "after_install") == AUDIT_SETUP
	assert _module_constant(hooks, "after_migrate") == AUDIT_SETUP


def test_tc_w0_018_trail_is_retrievable_over_the_api(repo_root):
	"""URS-W0-015 ("retrievable per record"): the trail is exposed as a whitelisted call."""
	tree = ast.parse((repo_root / "rheinwerk_mes/manufacturing_core/audit.py").read_text(encoding="utf-8"))
	whitelisted = {
		node.name
		for node in tree.body
		if isinstance(node, ast.FunctionDef)
		and any(
			isinstance(decorator, ast.Call)
			and isinstance(decorator.func, ast.Attribute)
			and decorator.func.attr == "whitelist"
			for decorator in node.decorator_list
		)
	}
	assert "get_audit_trail" in whitelisted


@pytest.fixture
def audit_api(site):
	"""The app module under test; imported through the site fixture because it needs frappe."""
	from rheinwerk_mes.manufacturing_core import audit

	return audit


@pytest.fixture
def technologist(site):
	"""Act as T. Schmid where the technologist fixture user exists (AC-1)."""
	user = TECHNOLOGIST if site.db.exists("User", TECHNOLOGIST) else "Administrator"
	site.set_user(user)
	return user


def _ensure(site, doctype, name, **values):
	"""Fetch a master record by name, creating it when the site has none."""
	if site.db.exists(doctype, name):
		return name
	return site.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


@pytest.fixture
def audited_item(site, technologist):
	"""A throwaway canonical Item; the `site` fixture rolls the transaction back."""
	item_group = _ensure(site, "Item Group", "Alle Artikelgruppen", item_group_name="Alle Artikelgruppen")
	uom = _ensure(site, "UOM", "Kg", uom_name="Kg")
	return site.get_doc(
		{
			"doctype": "Item",
			"item_code": "RW-TEST-AUDIT",
			"item_name": "Prüfharz Audit",
			"item_group": item_group,
			"stock_uom": uom,
		}
	).insert()


def test_tc_w0_018_master_data_doctypes_track_changes(site):
	"""URS-W0-015: change tracking is enabled on every canonical anchor through a
	committed Property Setter, not by hand."""
	for doctype in CANONICAL:
		assert site.get_meta(doctype).track_changes
		assert site.db.exists(
			"Property Setter",
			{"doc_type": doctype, "property": "track_changes", "value": "1"},
		)


def test_tc_w0_018_version_log_records_user_time_and_values(site, technologist, audited_item):
	"""AC-1: renaming an item as the technologist writes a Version entry naming the
	user, the timestamp and the old→new value of the changed field."""
	item = site.get_doc("Item", audited_item.name)
	before = item.item_name
	item.item_name = RENAMED
	item.save()

	version = site.get_all(
		"Version",
		filters={"ref_doctype": "Item", "docname": item.name},
		fields=["owner", "creation", "data"],
		order_by="creation desc",
		limit=1,
	)[0]
	assert version["owner"] == technologist
	assert version["creation"]
	changed = {row[0]: (row[1], row[2]) for row in json.loads(version["data"])["changed"]}
	assert changed["item_name"] == (before, RENAMED)


def test_tc_w0_018_audit_trail_covers_create_update_and_delete(site, audit_api, technologist, audited_item):
	"""URS-W0-015: one call returns the record's create, update and delete events in
	order, updates carrying the old→new value of each changed field."""
	item = site.get_doc("Item", audited_item.name)
	item.item_name = RENAMED
	item.save()

	trail = audit_api.get_audit_trail("Item", item.name)
	assert [entry["action"] for entry in trail] == ["create", "update"]
	update = trail[-1]
	assert update["user"] == technologist
	assert update["timestamp"]
	change = next(row for row in update["changes"] if row["field"] == "item_name")
	assert (change["old"], change["new"]) == (audited_item.item_name, RENAMED)

	site.delete_doc("Item", item.name)
	trail = audit_api.get_audit_trail("Item", item.name)
	assert [entry["action"] for entry in trail] == ["create", "update", "delete"]
	assert trail[-1]["user"] == technologist


def test_tc_w0_018_trail_rejects_non_canonical_doctypes(site, audit_api):
	"""URS-W0-015 scopes the trail to canonical master data; other doctypes are refused."""
	with pytest.raises(site.ValidationError):
		audit_api.get_audit_trail("User", "Administrator")
