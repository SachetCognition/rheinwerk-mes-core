"""Rollback of a migration run (URS-W0-011 AC-3, TC-W0-013).

The run journal written by `importer.import_extract` is replayed backwards: documents the
run inserted are deleted, documents it updated are restored to their journaled previous
values (including the `legacy_refs` rows and `uoms` child table it appended). Documents
the run never touched are left alone — rollback removes *exactly* that run's imports.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.integration.migration.importer import ImportResult, JournalEntry, read_journal


def _restore(entry: JournalEntry) -> None:
	if not frappe.db.exists(entry.doctype, entry.name):
		return
	doc = frappe.get_doc(entry.doctype, entry.name)
	previous: dict[str, Any] = entry.previous or {}
	for fieldname, value in previous.items():
		if fieldname in {"legacy_refs", "uoms"}:
			continue
		doc.set(fieldname, value)
	if "legacy_refs" in previous and doc.meta.get_field("legacy_refs"):
		doc.set("legacy_refs", [])
		for row in previous["legacy_refs"]:
			doc.append("legacy_refs", row)
	if "uoms" in previous and doc.meta.get_field("uoms"):
		doc.set("uoms", [])
		for row in previous["uoms"]:
			doc.append("uoms", row)
	doc.save(ignore_permissions=True)


def rollback_result(result: ImportResult) -> dict[str, int]:
	"""Reverse one import run; returns the number of deleted and restored documents."""
	deleted = restored = 0
	for entry in reversed(result.journal):
		if entry.action == "insert":
			if frappe.db.exists(entry.doctype, entry.name):
				frappe.delete_doc(
					entry.doctype, entry.name, force=True, ignore_permissions=True, delete_permanently=True
				)
				deleted += 1
		else:
			_restore(entry)
			restored += 1
	return {"deleted": deleted, "restored": restored}


def rollback_run(run_id: str) -> dict[str, int]:
	"""Reverse the import run `run_id` from its journal."""
	return rollback_result(read_journal(run_id))
