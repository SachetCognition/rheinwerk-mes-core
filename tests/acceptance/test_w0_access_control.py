"""W0 access-control baseline for canonical master data.

TC-W0-020 (URS-W0-017) — the technologist maintains master data; the planner and the
warehouse clerk read it only.
"""

from __future__ import annotations

import pytest

roles = pytest.importorskip("rheinwerk_mes.setup.roles")

ITEM_CODE = "RW-CHM-0001"
TECHNOLOGIST_USER = "t.schmid@rheinwerk-chemie.example"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"


@pytest.fixture
def item(site):
	"""The canonical item of TC-W0-020, created here when fixtures have not seeded it."""
	if not site.db.exists("Item", ITEM_CODE):
		site.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_CODE,
				"item_name": "Rheinol 40 Basisharz",
				"item_group": site.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)
	return ITEM_CODE


def test_permission_matrix_keeps_master_data_read_only_outside_the_technologist():
	"""URS-W0-017: only the technologist rule grants write/create on master data."""
	for role, doctypes, permissions in roles.PERMISSION_MATRIX:
		if set(doctypes) != set(roles.MASTER_DATA_DOCTYPES):
			continue
		expected_write = role == roles.TECHNOLOGIST
		assert permissions.get("read") == 1
		assert bool(permissions.get("write")) is expected_write
		assert bool(permissions.get("create")) is expected_write
		assert bool(permissions.get("delete")) is expected_write


def test_tc_w0_020_docperms_match_the_baseline(site):
	"""TC-W0-020: the applied Custom DocPerm rows carry the matrix onto the anchors."""
	for doctype in roles.MASTER_DATA_DOCTYPES:
		if not site.db.exists("DocType", doctype):
			continue
		perms = {
			row["role"]: row
			for row in site.get_all(
				"Custom DocPerm",
				filters={"parent": doctype, "role": ("in", roles.ROLES), "permlevel": 0},
				fields=["role", "read", "write", "create", "delete"],
			)
		}
		assert set(perms) == set(roles.ROLES), f"{doctype} is missing programme DocPerm rows"
		technologist = perms[roles.TECHNOLOGIST]
		assert (technologist["read"], technologist["write"], technologist["create"]) == (1, 1, 1)
		for role in (roles.PLANNER, roles.WAREHOUSE_CLERK):
			assert perms[role]["read"] == 1
			assert (perms[role]["write"], perms[role]["create"], perms[role]["delete"]) == (0, 0, 0)


def test_tc_w0_020_planner_cannot_modify_an_item(site, item):
	"""TC-W0-020 step 1 (URS-W0-017 AC-1): the planner may read the item but not save a change."""
	site.set_user(PLANNER_USER)
	doc = site.get_doc("Item", item)
	doc.item_name = "Planer-Änderung"
	with pytest.raises(site.PermissionError):
		doc.save()


def test_tc_w0_020_technologist_may_modify_an_item(site, item):
	"""TC-W0-020 step 2 (URS-W0-017 AC-2): the same edit succeeds for the technologist."""
	site.set_user(TECHNOLOGIST_USER)
	doc = site.get_doc("Item", item)
	doc.item_name = "Rheinol 40 Basisharz (Technologe)"
	doc.save()
	assert site.db.get_value("Item", item, "item_name") == "Rheinol 40 Basisharz (Technologe)"


def test_tc_w0_020_personas_hold_only_their_own_role(site):
	"""URS-W0-017 AC-1: P. Krüger holds the planner role only; T. Schmid the technologist."""
	assigned = {
		user: set(site.get_all("Has Role", filters={"parent": user}, pluck="role"))
		for user in (TECHNOLOGIST_USER, PLANNER_USER)
	}
	assert roles.TECHNOLOGIST in assigned[TECHNOLOGIST_USER]
	assert roles.PLANNER in assigned[PLANNER_USER]
	assert roles.TECHNOLOGIST not in assigned[PLANNER_USER]
