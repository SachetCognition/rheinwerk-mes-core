"""Site-backed loaders for the three independently-reversible W2 load steps.

The programme requires ``rollback(run_id)`` for *each* load step — batches, genealogy links
and state assignment — with the documented retention semantics (a genealogy-link rollback
keeps the batches URS-W2-030 created). Each loader therefore takes its own ``run_id`` and
writes its own run journal, reusing the W0-5 journal format (`importer.JournalEntry` /
`write_journal`) so `w2.rollback` can replay any one step backwards without disturbing the
others.

Design note (recorded in `docs/design/W2-migration.md`): URS-W2-030 maps the legacy
disposition (``BatchState`` / ``blockedForQualityControl`` / ERPNext ``disabled``) onto
``qa_state``, but the *assignment* is applied and journaled here as the state step so that a
qa_state-distribution mismatch rolls back the disposition alone (URS-W2-032 rollback
condition) while batch identity and links survive. The state step writes the
``qa_state_history`` audit row directly (not through `qa_state.transition`): the interactive
machine forbids the Quarantined→Quarantined entry note AC-1 needs, gates live reasons/roles
that do not apply to a historical fact, and refuses the reverse edges a bulk legacy load
legitimately reproduces. It writes only through the fields/child tables the genealogy module
owns — see the limitation note in the PR body.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from rheinwerk_mes.genealogy import links as genealogy_links
from rheinwerk_mes.integration.migration.importer import (
	ImportResult,
	JournalEntry,
	new_run_id,
	write_journal,
)
from rheinwerk_mes.integration.migration.w2.model import W2Extract

STEP_BATCHES = "batches"
STEP_LINKS = "links"
STEP_STATE = "state"

LINK_FIELD = genealogy_links.LINK_FIELD
HISTORY_FIELD = "qa_state_history"


def _run_id(step: str, extract: W2Extract, run_id: str | None) -> str:
	return run_id or new_run_id(f"w2{step}-{extract.plant}")


def _result(
	step: str, extract: W2Extract, run_id: str, journal: list[JournalEntry], count: int
) -> ImportResult:
	result = ImportResult(
		run_id=run_id,
		source=f"w2-{step}-{extract.plant}",
		imported={step: count},
		deferred={},
		journal=journal,
	)
	write_journal(result)
	return result


# --------------------------------------------------------------------------------------
# Step 1 — canonical batch identity (URS-W2-030)
# --------------------------------------------------------------------------------------


def load_batches(extract: W2Extract, *, run_id: str | None = None) -> ImportResult:
	"""Merge the legacy dual model into canonical `Batch` identity records (URS-W2-030).

	Sets batch_id, item, expiry (earliest of conflicting lots), `legacy_refs`, the original
	quantity and supplier batch, and flags orphan resource strings `genealogy_incomplete`.
	The disposition (`qa_state`) is left at the Quarantined entry default and assigned by
	`load_state`; genealogy links and the trace-boundary flag are added by `load_links`.
	"""
	run_id = _run_id(STEP_BATCHES, extract, run_id)
	journal: list[JournalEntry] = []
	count = 0
	for staged in extract.sorted_batches():
		# The trace-boundary incompleteness (Plant B) is a genealogy-load fact; only the
		# orphan-identity incompleteness (URS-W2-030 AC-2) is set here.
		incomplete_now = (
			staged.genealogy_incomplete and staged.batch_id not in extract.incomplete_boundary_batches
		)
		if frappe.db.exists("Batch", staged.batch_id):
			journal.append(_update_batch_identity(staged, incomplete_now))
		else:
			journal.append(_insert_batch(staged, incomplete_now))
		count += 1
	return _result(STEP_BATCHES, extract, run_id, journal, count)


def _insert_batch(staged: Any, incomplete_now: bool) -> JournalEntry:
	doc = frappe.get_doc(
		{
			"doctype": "Batch",
			"batch_id": staged.batch_id,
			"item": staged.item,
			"expiry_date": staged.expiry_date,
			"genealogy_incomplete": 1 if incomplete_now else 0,
		}
	)
	if doc.meta.has_field("qty_original") and staged.qty_original is not None:
		doc.qty_original = staged.qty_original
	if doc.meta.has_field("supplier_batch_no") and staged.supplier_batch_no:
		doc.supplier_batch_no = staged.supplier_batch_no
	for ref in staged.legacy_refs:
		doc.append(
			"legacy_refs",
			{
				"source_system": ref.source_system,
				"source_entity": ref.source_entity,
				"source_identifier": ref.source_identifier,
				"migrated_on": now_datetime(),
			},
		)
	doc.insert(ignore_permissions=True)
	return JournalEntry("Batch", doc.name, "insert")


def _update_batch_identity(staged: Any, incomplete_now: bool) -> JournalEntry:
	doc = frappe.get_doc("Batch", staged.batch_id)
	previous = _snapshot(
		doc,
		fields=("expiry_date", "genealogy_incomplete", "qty_original", "supplier_batch_no"),
		tables=("legacy_refs",),
	)
	doc.expiry_date = staged.expiry_date
	doc.genealogy_incomplete = 1 if incomplete_now else 0
	if doc.meta.has_field("qty_original") and staged.qty_original is not None:
		doc.qty_original = staged.qty_original
	if doc.meta.has_field("supplier_batch_no") and staged.supplier_batch_no:
		doc.supplier_batch_no = staged.supplier_batch_no
	existing = {(row.source_system, row.source_identifier) for row in (doc.get("legacy_refs") or [])}
	for ref in staged.legacy_refs:
		if (ref.source_system, ref.source_identifier) in existing:
			continue
		doc.append(
			"legacy_refs",
			{
				"source_system": ref.source_system,
				"source_entity": ref.source_entity,
				"source_identifier": ref.source_identifier,
				"migrated_on": now_datetime(),
			},
		)
	doc.save(ignore_permissions=True)
	return JournalEntry("Batch", doc.name, "update", previous)


# --------------------------------------------------------------------------------------
# Step 2 — genealogy links + trace boundary (URS-W2-031)
# --------------------------------------------------------------------------------------


def load_links(extract: W2Extract, *, run_id: str | None = None) -> ImportResult:
	"""Fold the legacy used/produced trees onto the produced canonical Batches (URS-W2-031).

	One `produced` self-link and one `consumed` link per used batch are written onto each
	produced batch, quantities preserved one-to-one. Plant B produced batches whose input
	lacked a `lotId` are flagged `genealogy_incomplete` with the plant-wide trace-boundary
	date, so the trace terminates explicitly rather than silently (AC-2).
	"""
	run_id = _run_id(STEP_LINKS, extract, run_id)
	journal: list[JournalEntry] = []

	by_produced: dict[str, list[Any]] = {}
	for link in extract.links:
		by_produced.setdefault(link.produced_batch, []).append(link)

	count = 0
	for produced_batch in sorted(by_produced):
		rows = by_produced[produced_batch]
		doc = frappe.get_doc("Batch", produced_batch)
		if not doc.meta.has_field(LINK_FIELD):
			continue
		previous = _snapshot(
			doc,
			fields=("genealogy_incomplete", "trace_boundary_date"),
			tables=(LINK_FIELD,),
		)
		for link in rows:
			doc.append(
				LINK_FIELD,
				{
					"direction": link.direction,
					"batch": link.batch,
					"item": link.item,
					"qty": link.qty,
					"uom": link.uom,
				},
			)
		if produced_batch in extract.incomplete_boundary_batches:
			doc.genealogy_incomplete = 1
			if doc.meta.has_field("trace_boundary_date") and extract.trace_boundary_date:
				doc.trace_boundary_date = extract.trace_boundary_date
		doc.save(ignore_permissions=True)
		journal.append(JournalEntry("Batch", doc.name, "update", previous))
		count += len(rows)
	return _result(STEP_LINKS, extract, run_id, journal, count)


# --------------------------------------------------------------------------------------
# Step 3 — qa_state assignment + history (URS-W2-030 mapping / URS-W2-032 history)
# --------------------------------------------------------------------------------------


def load_state(extract: W2Extract, *, run_id: str | None = None) -> ImportResult:
	"""Assign the legacy disposition to `qa_state` and record its origin (URS-W2-032).

	Blocked/Quarantined batches get a `qa_state_history` row naming the legacy flag as the
	origin (AC-1). No parametric Quality Inspection is created — the flags live purely as
	qa_state history/notes (AC-2). Journaled independently so a qa_state mismatch rolls back
	the disposition alone.
	"""
	run_id = _run_id(STEP_STATE, extract, run_id)
	journal: list[JournalEntry] = []
	count = 0
	for staged in extract.sorted_batches():
		name = staged.batch_id
		doc_before = frappe.get_doc("Batch", name)
		previous = _snapshot(doc_before, fields=("qa_state", "qa_state_reason"), tables=(HISTORY_FIELD,))
		from_state = doc_before.get("qa_state") or "Quarantined"

		# Set disposition without the interactive machine (historical fact), then record
		# the audit row citing the legacy origin.
		frappe.db.set_value(
			"Batch",
			name,
			{"qa_state": staged.qa_state, "qa_state_reason": staged.qa_state_origin},
			update_modified=False,
		)
		if staged.qa_state_origin:
			doc = frappe.get_doc("Batch", name)
			doc.append(
				HISTORY_FIELD,
				{
					"from_state": from_state,
					"to_state": staged.qa_state,
					"changed_by": frappe.session.user,
					"changed_at": now_datetime(),
					"reason": staged.qa_state_origin,
					"triggering_document": run_id,
				},
			)
			doc.save(ignore_permissions=True)
		journal.append(JournalEntry("Batch", name, "update", previous))
		count += 1
	return _result(STEP_STATE, extract, run_id, journal, count)


# --------------------------------------------------------------------------------------
# Journal snapshots (W2-aware: scalar fields + child tables)
# --------------------------------------------------------------------------------------


def _snapshot(doc: Any, *, fields: tuple[str, ...], tables: tuple[str, ...]) -> dict[str, Any]:
	"""Reversible snapshot understood by `w2.rollback` (fields + child-table rows)."""
	snapshot: dict[str, Any] = {"_w2": True, "fields": {}, "tables": {}}
	for name in fields:
		if doc.meta.has_field(name):
			snapshot["fields"][name] = doc.get(name)
	for table in tables:
		if not doc.meta.has_field(table):
			continue
		snapshot["tables"][table] = [
			{key: value for key, value in row.as_dict().items() if not key.startswith("_")}
			for row in (doc.get(table) or [])
		]
	return snapshot
