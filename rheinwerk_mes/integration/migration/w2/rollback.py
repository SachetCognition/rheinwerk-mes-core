"""Per-step, W2-aware rollback by run id (URS-W2-030…032 rollback conditions).

Extends the W0-5 rollback (which restores scalar master-data fields) so it can also revert
the child tables a batch-level load touches — `genealogy_links` and `qa_state_history` — and
restore `qa_state` without tripping the interactive state machine. Reversing one step's
journal never touches another step's records, which is what gives the load steps their
independent retention semantics:

* rolling back the **links** step keeps the batches URS-W2-030 created (only the
  `genealogy_links` rows and the trace-boundary flag are removed);
* rolling back the **state** step keeps identity and links (only `qa_state` /
  `qa_state_history` revert);
* rolling back the **batches** step deletes exactly the batches it inserted.
"""

from __future__ import annotations

import frappe

from rheinwerk_mes.integration.migration.importer import ImportResult, JournalEntry, read_journal


def rollback_result(result: ImportResult) -> dict[str, int]:
	"""Reverse one W2 load run; returns deleted / restored document counts."""
	deleted = restored = 0
	for entry in reversed(result.journal):
		if entry.action == "insert":
			if frappe.db.exists(entry.doctype, entry.name):
				frappe.delete_doc(
					entry.doctype,
					entry.name,
					force=True,
					ignore_permissions=True,
					delete_permanently=True,
				)
				deleted += 1
		else:
			_restore(entry)
			restored += 1
	return {"deleted": deleted, "restored": restored}


def rollback_run(run_id: str) -> dict[str, int]:
	"""Reverse the W2 load run `run_id` from its journal (does not commit — see `cli`)."""
	return rollback_result(read_journal(run_id))


def _restore(entry: JournalEntry) -> None:
	previous = entry.previous or {}
	if not previous.get("_w2"):
		# A non-W2 (master-data) journal — defer to the W0 restore semantics.
		from rheinwerk_mes.integration.migration.rollback import _restore as w0_restore

		w0_restore(entry)
		return

	if not frappe.db.exists(entry.doctype, entry.name):
		return

	scalar_fields = previous.get("fields", {})
	if scalar_fields:
		# db-level so a qa_state revert (e.g. Released→Quarantined) never has to pass the
		# interactive transition machine, which would forbid the reverse edge.
		frappe.db.set_value(entry.doctype, entry.name, scalar_fields, update_modified=False)

	tables = previous.get("tables", {})
	if tables:
		doc = frappe.get_doc(entry.doctype, entry.name)
		for table, rows in tables.items():
			if doc.meta.has_field(table):
				doc.set(table, rows)
		doc.save(ignore_permissions=True)


def rollback_runs(run_ids: list[str]) -> dict[str, dict[str, int]]:
	"""Reverse several steps; caller passes them in the intended teardown order."""
	return {run_id: rollback_run(run_id) for run_id in run_ids}
