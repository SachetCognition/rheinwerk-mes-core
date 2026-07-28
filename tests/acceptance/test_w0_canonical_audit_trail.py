"""W0 audit trail on canonical master data.

TC-W0-018 (URS-W0-015) — Frappe document versioning records who changed what, when.
"""

from __future__ import annotations

import json

TECHNOLOGIST = "t.schmid@rheinwerk-chemie.example"
AUDITED = ("Item", "Workstation", "BOM", "Routing", "Work Order", "Warehouse")


def test_tc_w0_018_master_data_doctypes_track_changes(site):
	"""TC-W0-018 (URS-W0-015 AC-1): change tracking is enabled on every canonical
	master-data anchor through a committed Property Setter, not by hand."""
	for doctype in AUDITED:
		assert site.get_meta(doctype).track_changes
		assert site.db.exists(
			"Property Setter",
			{"doc_type": doctype, "property": "track_changes", "value": "1"},
		)


def test_tc_w0_018_version_log_records_user_time_and_values(site):
	"""TC-W0-018 (URS-W0-015 AC-1+AC-2): editing an Item as the technologist writes a
	Version entry naming the user, the timestamp and the old/new value."""
	site.set_user(TECHNOLOGIST)
	item = site.get_doc("Item", "RW-CHM-0001")
	before = item.item_name
	item.item_name = "Rheinol 40 Basisharz (Rev. B)"
	item.save()

	version = site.get_all(
		"Version",
		filters={"ref_doctype": "Item", "docname": item.name},
		fields=["owner", "creation", "data"],
		order_by="creation desc",
		limit=1,
	)[0]
	assert version["owner"] == TECHNOLOGIST
	assert version["creation"]
	changed = {row[0]: (row[1], row[2]) for row in json.loads(version["data"])["changed"]}
	assert changed["item_name"] == (before, "Rheinol 40 Basisharz (Rev. B)")
