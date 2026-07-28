"""W0 access-control baseline for canonical master data.

TC-W0-020 (URS-W0-017) — technologist maintains master data; planner and warehouse
clerk read it only.
"""

from __future__ import annotations

import pytest

TECHNOLOGIST = "t.schmid@rheinwerk-chemie.example"
PLANNER = "p.krueger@rheinwerk-chemie.example"
WAREHOUSE_CLERK = "w.braun@rheinwerk-chemie.example"
MASTER_DATA = ("Item", "Workstation", "BOM", "Routing", "Warehouse", "UOM")


def test_tc_w0_020_role_matrix_is_read_only_outside_the_technologist_role(site):
	"""TC-W0-020 (URS-W0-017 AC-1): on every master-data DocType the technologist role
	may create and write, while planner and warehouse clerk hold read only."""
	for doctype in MASTER_DATA:
		perms = {
			row["role"]: row
			for row in site.get_all(
				"Custom DocPerm",
				filters={"parent": doctype, "role": ("like", "Rheinwerk%")},
				fields=["role", "read", "write", "create", "delete"],
			)
		}
		technologist = perms["Rheinwerk Technologist"]
		assert (technologist["read"], technologist["write"], technologist["create"]) == (1, 1, 1)
		for role in ("Rheinwerk Planner", "Rheinwerk Warehouse Clerk"):
			assert perms[role]["read"] == 1
			assert perms[role]["write"] == 0
			assert perms[role]["create"] == 0
			assert perms[role]["delete"] == 0


def test_tc_w0_020_planner_cannot_modify_an_item(site):
	"""TC-W0-020 step 1 (URS-W0-017 AC-2): the planner persona may read RW-CHM-0001 but
	saving a change is refused."""
	site.set_user(PLANNER)
	item = site.get_doc("Item", "RW-CHM-0001")
	assert item.item_name
	item.item_name = "Planer-Änderung"
	with pytest.raises(site.PermissionError):
		item.save()


def test_tc_w0_020_warehouse_clerk_cannot_modify_a_work_centre(site):
	"""TC-W0-020 step 1 (URS-W0-017 AC-2): the warehouse clerk is read-only on work
	centres too."""
	site.set_user(WAREHOUSE_CLERK)
	workstation = site.get_doc("Workstation", "MIX-01")
	workstation.production_line = None
	with pytest.raises(site.PermissionError):
		workstation.save()


def test_tc_w0_020_technologist_may_modify_master_data(site):
	"""TC-W0-020 step 2 (URS-W0-017 AC-2): the same edit succeeds for the technologist."""
	site.set_user(TECHNOLOGIST)
	item = site.get_doc("Item", "RW-CHM-0001")
	item.item_name = "Rheinol 40 Basisharz (Technologe)"
	item.save()
	assert site.db.get_value("Item", "RW-CHM-0001", "item_name") == "Rheinol 40 Basisharz (Technologe)"


def test_tc_w0_020_personas_carry_the_programme_roles(site):
	"""TC-W0-020 (URS-W0-017 AC-1): the seeded personas hold the roles the baseline
	grants, created by committed setup code."""
	assigned = {
		user: set(site.get_all("Has Role", filters={"parent": user}, pluck="role"))
		for user in (TECHNOLOGIST, PLANNER, WAREHOUSE_CLERK)
	}
	assert "Rheinwerk Technologist" in assigned[TECHNOLOGIST]
	assert "Rheinwerk Planner" in assigned[PLANNER]
	assert "Rheinwerk Warehouse Clerk" in assigned[WAREHOUSE_CLERK]
	assert "Rheinwerk Technologist" not in assigned[PLANNER] | assigned[WAREHOUSE_CLERK]
