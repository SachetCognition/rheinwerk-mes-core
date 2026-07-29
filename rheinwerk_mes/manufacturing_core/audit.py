"""Per-record audit trail over the platform version/audit mechanism (URS-W0-015).

The substrate stores the three lifecycle events of a canonical master-data record
in three different places:

* **create** — the record's own `owner`/`creation` stamps (Frappe writes a
  `Version` row on insert only for imports, which carry `updater_reference`);
* **update** — one `Version` row per save, holding the old→new value of every
  changed field (requires `track_changes`, asserted in
  `rheinwerk_mes.setup.property_setters`);
* **delete** — a `Deleted Document` row naming the deleting user and carrying a
  snapshot of the deleted record.

`get_audit_trail` folds them into a single chronological trail so the requirement
"retrievable per record" holds for one call, whether or not the record still exists.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime

from rheinwerk_mes.setup.property_setters import AUDITED_DOCTYPES

CREATE = "create"
UPDATE = "update"
DELETE = "delete"


def _label(doctype: str, fieldname: str) -> str:
	"""Human-readable (translated) label for a field, falling back to its name."""
	field = frappe.get_meta(doctype).get_field(fieldname)
	return _(field.label) if field and field.label else fieldname


def _change(doctype: str, fieldname: str, old: Any, new: Any) -> dict[str, Any]:
	return {"field": fieldname, "label": _label(doctype, fieldname), "old": old, "new": new}


def _changes_from_version(doctype: str, data: dict[str, Any]) -> list[dict[str, Any]]:
	"""Flatten a `Version` diff into one row per changed field, child rows included."""
	changes = [_change(doctype, row[0], row[1], row[2]) for row in data.get("changed", [])]

	for table_field, _index, _row_name, child_changes in data.get("row_changed", []):
		for row in child_changes:
			changes.append(_change(doctype, table_field, row[1], row[2]))

	for table_field, row in data.get("added", []):
		changes.append({"field": table_field, "label": _label(doctype, table_field), "old": None, "new": row})

	for table_field, row in data.get("removed", []):
		changes.append({"field": table_field, "label": _label(doctype, table_field), "old": row, "new": None})

	return changes


def _create_entry(doctype: str, name: str, snapshots: list[dict[str, Any]]) -> dict[str, Any] | None:
	"""Creation event of the live record, or of its `Deleted Document` snapshot."""
	record = frappe.db.get_value(doctype, name, ["owner", "creation"], as_dict=True)
	if not record:
		record = next((snapshot for snapshot in snapshots if snapshot.get("creation")), None)
	if not record:
		return None
	return {
		"action": CREATE,
		"user": record["owner"],
		"timestamp": get_datetime(record["creation"]),
		"changes": [],
	}


def _update_entries(doctype: str, name: str) -> list[dict[str, Any]]:
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": name},
		fields=["owner", "creation", "data"],
		order_by="creation asc",
	)
	entries = []
	for version in versions:
		data = json.loads(version.data or "{}")
		changes = _changes_from_version(doctype, data)
		if not changes:
			# Insert-time rows written by data imports carry no field diff.
			continue
		entries.append(
			{
				"action": UPDATE,
				"user": version.owner,
				"timestamp": get_datetime(version.creation),
				"changes": changes,
			}
		)
	return entries


def _delete_entries(doctype: str, name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	"""Delete events plus the record snapshots they carry."""
	deletions = frappe.get_all(
		"Deleted Document",
		filters={"deleted_doctype": doctype, "deleted_name": name},
		fields=["owner", "creation", "data"],
		order_by="creation asc",
	)
	entries = [
		{
			"action": DELETE,
			"user": deletion.owner,
			"timestamp": get_datetime(deletion.creation),
			"changes": [],
		}
		for deletion in deletions
	]
	snapshots = [json.loads(deletion.data or "{}") for deletion in deletions]
	return entries, snapshots


@frappe.whitelist()
def get_audit_trail(doctype: str, name: str) -> list[dict[str, Any]]:
	"""Chronological create/update/delete trail of one canonical master-data record.

	Each entry carries the acting user, the timestamp and — for updates — the
	old→new value of every changed field.
	"""
	if doctype not in AUDITED_DOCTYPES:
		frappe.throw(
			_("{0} ist keine auditierte Stammdaten-Entität.").format(_(doctype)),
			title=_("Kein Audit-Trail"),
		)
	frappe.has_permission(doctype, "read", throw=True)

	deleted, snapshots = _delete_entries(doctype, name)
	entries = _update_entries(doctype, name) + deleted
	created = _create_entry(doctype, name, snapshots)
	if created:
		entries.append(created)
	if not entries:
		frappe.throw(
			_("Datensatz {0} {1} existiert nicht.").format(_(doctype), name),
			frappe.DoesNotExistError,
		)

	entries.sort(key=lambda entry: entry["timestamp"])
	return entries
