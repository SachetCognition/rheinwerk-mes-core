"""Genealogy links as system-of-record (W2-1 · URS-W2-001, URS-W2-004).

Every batch-managed consumption and production of a production order is recorded as a
`Genealogy Link` row **on the produced canonical Batch** — not derived from stock-ledger
joins at read time. The links are the trace source; the ledger stays the quantity truth,
and `reconcile_work_order()` proves the two agree (URS-W2-001 AC-2).

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/
advancedGenealogy/constants/TrackingRecordFields.java:31-49` — a Qcadoo tracking record
holds one `producedBatch` and n `usedBatchesSimple` rows with quantities. The Rheinwerk
re-implementation folds the tracking record into the produced Batch itself (ADR-003/CDM-01
`genealogy_links`), keeping one object per lot instead of a second parallel entity.

Write path: the anchor `Stock Entry` `on_submit`/`on_cancel` hooks call
`rebuild_links_for_work_order()`, which recomputes the whole link set of the order's
produced batches from every submitted Stock Entry of that order. Recomputation (rather
than incremental appends) is what makes a cancel-and-repost correct within the same
transaction (URS-W2-001 AC-2): the corrected quantity replaces the old one, no stale row
survives. Non-batch-managed materials (process water) simply have no batch and therefore
produce no link — the produced batch stays complete (URS-W2-001 AC-3).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

CONSUMED = "consumed"
PRODUCED = "produced"

LINK_FIELD = "genealogy_links"


def _batch_managed(item: str) -> bool:
	return bool(frappe.db.get_value("Item", item, "has_batch_no"))


def row_batches(row: Any) -> list[str]:
	"""Batches a Stock Entry row moves — legacy `batch_no` field or its bundle."""
	if row.get("batch_no"):
		return [row.batch_no]
	bundle = row.get("serial_and_batch_bundle")
	if not bundle:
		return []
	return [
		batch
		for batch in frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, pluck="batch_no")
		if batch
	]


def _entries_of(work_order: str) -> list[str]:
	return frappe.get_all("Stock Entry", filters={"work_order": work_order, "docstatus": 1}, pluck="name")


def movements_of(work_order: str) -> dict[str, list[dict[str, Any]]]:
	"""Consumed / produced batch movements of `work_order` from its submitted entries.

	The returned mapping is the shape the links are written from and the shape the
	reconciliation compares against, so both read the same ledger facts.
	"""
	consumed: dict[tuple[str, str], dict[str, Any]] = {}
	produced: dict[str, dict[str, Any]] = {}
	for entry_name in _entries_of(work_order):
		entry = frappe.get_doc("Stock Entry", entry_name)
		for row in entry.items:
			if not _batch_managed(row.item_code):
				continue
			for batch in row_batches(row):
				if row.get("s_warehouse") and not row.get("t_warehouse"):
					key = (batch, row.item_code)
					bucket = consumed.setdefault(
						key,
						{"batch": batch, "item": row.item_code, "qty": 0.0, "uom": row.get("stock_uom")},
					)
					bucket["qty"] += flt(row.qty)
				elif row.get("t_warehouse") and not row.get("s_warehouse"):
					bucket = produced.setdefault(
						batch,
						{"batch": batch, "item": row.item_code, "qty": 0.0, "uom": row.get("stock_uom")},
					)
					bucket["qty"] += flt(row.qty)
	return {CONSUMED: list(consumed.values()), PRODUCED: list(produced.values())}


def rebuild_links_for_work_order(work_order: str) -> list[str]:
	"""Recompute the genealogy links of every batch `work_order` produced.

	Returns the produced batch names. Each produced batch receives one `produced` link
	naming the order and its output quantity, plus one `consumed` link per batch-managed
	input batch with the quantity consumed by the order (URS-W2-001 AC-1).
	"""
	if not work_order:
		return []
	movements = movements_of(work_order)
	touched: list[str] = []
	for output in movements[PRODUCED]:
		batch = frappe.get_doc("Batch", output["batch"])
		if not batch.meta.has_field(LINK_FIELD):
			continue
		kept = [
			row
			for row in batch.get(LINK_FIELD) or []
			if row.production_order != work_order  # links of other orders stay untouched
		]
		batch.set(LINK_FIELD, [])
		for row in kept:
			batch.append(LINK_FIELD, row.as_dict())
		batch.append(
			LINK_FIELD,
			{
				"direction": PRODUCED,
				"batch": output["batch"],
				"item": output["item"],
				"qty": output["qty"],
				"uom": output.get("uom"),
				"production_order": work_order,
			},
		)
		for used in movements[CONSUMED]:
			batch.append(
				LINK_FIELD,
				{
					"direction": CONSUMED,
					"batch": used["batch"],
					"item": used["item"],
					"qty": used["qty"],
					"uom": used.get("uom"),
					"production_order": work_order,
				},
			)
		batch.flags.ignore_permissions = True
		batch.save(ignore_permissions=True)
		touched.append(batch.name)
	return touched


def links_of(batch: str, direction: str | None = None) -> list[dict[str, Any]]:
	"""Genealogy links recorded on `batch`, optionally filtered by direction."""
	doc = frappe.get_doc("Batch", batch)
	rows = [
		{
			"direction": row.direction,
			"batch": row.batch,
			"item": row.item,
			"qty": flt(row.qty),
			"uom": row.uom,
			"production_order": row.production_order,
		}
		for row in doc.get(LINK_FIELD) or []
	]
	return [row for row in rows if direction is None or row["direction"] == direction]


def consumers_of(batch: str) -> list[dict[str, Any]]:
	"""Produced batches that consumed `batch` — the forward-trace edge (URS-W2-002)."""
	rows = frappe.get_all(
		"Genealogy Link",
		filters={"direction": CONSUMED, "batch": batch, "parenttype": "Batch"},
		fields=["parent as produced_batch", "qty", "uom", "item", "production_order"],
		order_by="parent asc",
	)
	return [dict(row) for row in rows]


def reconcile_work_order(work_order: str) -> list[dict[str, Any]]:
	"""Divergent rows between the recorded links and the ledger movements (URS-W2-001 AC-2).

	An empty list is the pass condition of TC-W2-002 step 2: the system-of-record and the
	stock-ledger-derived trace agree row for row.
	"""
	movements = movements_of(work_order)
	divergences: list[dict[str, Any]] = []
	for output in movements[PRODUCED]:
		recorded = {
			(row["direction"], row["batch"]): row["qty"]
			for row in links_of(output["batch"])
			if row["production_order"] == work_order
		}
		expected = {(PRODUCED, output["batch"]): output["qty"]}
		expected.update({(CONSUMED, used["batch"]): used["qty"] for used in movements[CONSUMED]})
		for key in set(expected) | set(recorded):
			if flt(expected.get(key, 0.0), 6) != flt(recorded.get(key, 0.0), 6):
				divergences.append(
					{
						"produced_batch": output["batch"],
						"direction": key[0],
						"batch": key[1],
						"ledger_qty": expected.get(key, 0.0),
						"link_qty": recorded.get(key, 0.0),
					}
				)
	return divergences


def mark_incomplete(batch: str, trace_boundary_date: str | None = None) -> None:
	"""Flag a batch whose lineage is not fully recorded (URS-W2-004 AC-1).

	Used by the migration when a legacy resource batch string has no matched genealogy
	batch, and for Plant B history behind the trace boundary, where the boundary date is
	recorded alongside the flag so the trace does not silently terminate (AC-2).
	"""
	values: dict[str, Any] = {"genealogy_incomplete": 1}
	if trace_boundary_date:
		values["trace_boundary_date"] = trace_boundary_date
	frappe.db.set_value("Batch", batch, values)


def is_incomplete(batch: str) -> bool:
	return bool(frappe.db.get_value("Batch", batch, "genealogy_incomplete"))


# --------------------------------------------------------------------------------------
# Document hooks (registered in hooks.py)
# --------------------------------------------------------------------------------------


def on_stock_entry_submit(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.on_submit` — (re)write the genealogy of the order's produced batches."""
	rebuild_links_for_work_order(doc.get("work_order"))


def on_stock_entry_cancel(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.on_cancel` — the cancelled movement leaves the link set immediately."""
	rebuild_links_for_work_order(doc.get("work_order"))
