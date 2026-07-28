"""Repacking journey — split/merge batch quantity across handling units (W2-8 · URS-W2-027).

A Repacking is a `draft → accepted` journey (or `→ rejected`) that moves `qty` of a batch
from a source Handling Unit to a target Handling Unit. Two shapes:

* **same identity** — the batch identity is preserved (AC-1). Because a Handling Unit is a
  *reference* layer over the anchor ledger (ADR-005/CDM-03), moving stock between two units
  of the same warehouse and batch changes only the units' content rows; the ledger balance
  of the batch is untouched, so no quantity is invented or lost.
* **new lot identity** — a re-drumming/re-labelling that mints a new lot (AC-2). A new
  canonical Batch is created carrying `parent_batch = <source>`; the quantity is issued
  from the source batch and received onto the new batch in the same warehouse, leaving the
  item's on-hand total unchanged. The `parent_batch` split lineage is deliberately distinct
  from production genealogy (`genealogy_links`): a repack writes **no** Genealogy Link.

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`materialFlowResources/states/constants/RepackingState.java` — DRAFT → {ACCEPTED, REJECTED},
both terminal. `parent_batch` re-expresses CDM-01 "split/repack lineage, distinct from
genealogy".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from rheinwerk_mes.warehouse import journey, movements
from rheinwerk_mes.warehouse.availability import ledger_balance

WORKFLOW_NAME = "Repacking Journey"

PARENT_BATCH_FIELD = "parent_batch"

#: Qcadoo `RepackingState.canChangeTo`: DRAFT → {ACCEPTED, REJECTED}; both terminal.
JOURNEY = journey.Journey(
	workflow_name=WORKFLOW_NAME,
	state_field="state",
	transitions={
		journey.DRAFT: frozenset({journey.ACCEPTED, journey.REJECTED}),
		journey.ACCEPTED: frozenset(),
		journey.REJECTED: frozenset(),
	},
	initial=journey.DRAFT,
	reason_required=frozenset({journey.REJECTED}),
)


def assert_repack_feasible(doc: Any) -> None:
	"""Refuse a repack that would draw more than the source holds (no invented quantity)."""
	qty = Decimal(str(flt(doc.qty)))
	if qty <= 0:
		frappe.throw(_("Die umzupackende Menge muss größer als 0 sein."), title=_("Umpacken abgelehnt"))
	balance = ledger_balance(doc.item, doc.warehouse, doc.batch_no, consider_expired=True)
	if qty > balance:
		frappe.throw(
			_("Es sollen {0} kg umgepackt werden, im Lager liegen aber nur {1} kg der Charge {2}.").format(
				float(qty), float(balance), doc.batch_no
			),
			title=_("Umpacken abgelehnt"),
		)


def _content_row(handling_unit: str, item: str, batch_no: str | None) -> Any | None:
	for row in handling_unit.get("contents") or []:
		if row.item == item and (row.batch_no or None) == (batch_no or None):
			return row
	return None


def adjust_handling_unit(hu_name: str, item: str, batch_no: str, delta: Decimal, uom: str) -> None:
	"""Add `delta` (kg) of `(item, batch)` to a Handling Unit's reference content.

	A negative delta reduces (and prunes at zero) the matching row; a positive delta tops it
	up or appends it. Saving re-runs the unit's ledger reconciliation flag — the reference
	can never claim more than the ledger holds without being flagged (URS-W1-018).
	"""
	unit = frappe.get_doc("Handling Unit", hu_name)
	row = _content_row(unit, item, batch_no)
	current = Decimal(str(flt(row.qty))) if row else Decimal("0")
	new_qty = current + delta
	if row is None:
		if new_qty > 0:
			unit.append("contents", {"item": item, "batch_no": batch_no, "qty": float(new_qty), "uom": uom})
	elif new_qty <= 0:
		unit.remove(row)
	else:
		row.qty = float(new_qty)
	unit.flags.ignore_permissions = True
	unit.save(ignore_permissions=True)


def _create_split_batch(doc: Any) -> str:
	"""Mint the new lot with `parent_batch` set to the source batch (AC-2)."""
	source = frappe.get_doc("Batch", doc.batch_no)
	new_batch = frappe.get_doc(
		{
			"doctype": "Batch",
			"item": doc.item,
			"manufacturing_date": source.get("manufacturing_date"),
			"expiry_date": source.get("expiry_date"),
		}
	)
	if doc.get("new_batch_id"):
		new_batch.batch_id = doc.new_batch_id
	if new_batch.meta.has_field(PARENT_BATCH_FIELD):
		new_batch.set(PARENT_BATCH_FIELD, doc.batch_no)
	if new_batch.meta.has_field("storage_location") and doc.get("target_handling_unit"):
		new_batch.storage_location = frappe.db.get_value(
			"Handling Unit", doc.target_handling_unit, "storage_location"
		)
	new_batch.insert(ignore_permissions=True)
	return new_batch.name


def _valuation_rate(item: str, warehouse: str, batch_no: str) -> float:
	rate = frappe.db.get_value(
		"Stock Ledger Entry",
		{"item_code": item, "warehouse": warehouse, "batch_no": batch_no, "is_cancelled": 0},
		"valuation_rate",
		order_by="posting_date desc, posting_time desc, creation desc",
	)
	if rate:
		return float(rate)
	return float(frappe.db.get_value("Item", item, "valuation_rate") or 0) or 1.0


def perform_repack(doc: Any) -> None:
	"""Execute the accepted repack — reference-only split, or a new-lot ledger split."""
	qty = Decimal(str(flt(doc.qty)))
	uom = doc.get("uom") or frappe.db.get_value("Item", doc.item, "stock_uom")

	if not doc.creates_new_lot:
		# Same batch identity: a reference move between handling units, no ledger movement.
		adjust_handling_unit(doc.source_handling_unit, doc.item, doc.batch_no, -qty, uom)
		adjust_handling_unit(doc.target_handling_unit, doc.item, doc.batch_no, qty, uom)
		return

	new_batch = _create_split_batch(doc)
	rate = _valuation_rate(doc.item, doc.warehouse, doc.batch_no)
	# Issue the source lot and receive the new lot in the same warehouse: the item's
	# on-hand total is unchanged, only the batch identity of `qty` kg changes.
	issue = movements.book_movement(
		document_type="RELEASE",
		item=doc.item,
		qty=float(qty),
		batch_no=doc.batch_no,
		company=doc.company,
		source_warehouse=doc.warehouse,
	)
	receipt = movements.book_movement(
		document_type="RECEIPT",
		item=doc.item,
		qty=float(qty),
		batch_no=new_batch,
		company=doc.company,
		target_warehouse=doc.warehouse,
		storage_location=frappe.db.get_value("Handling Unit", doc.target_handling_unit, "storage_location"),
		handling_unit=doc.target_handling_unit,
		basic_rate=rate,
	)
	adjust_handling_unit(doc.source_handling_unit, doc.item, doc.batch_no, -qty, uom)
	adjust_handling_unit(doc.target_handling_unit, doc.item, new_batch, qty, uom)
	frappe.db.set_value("Repacking", doc.name, {"new_batch": new_batch, "repack_stock_entry": receipt})
	doc.new_batch = new_batch
	doc.repack_stock_entry = receipt
	# `issue` is recorded implicitly on the ledger; the finished-lot receipt is the entry a
	# clerk follows from the repack, so it is the one surfaced on the document.
	del issue


@frappe.whitelist()
def split_lineage(batch: str) -> dict[str, Any]:
	"""Repack/split lineage of `batch` via `parent_batch` — distinct from genealogy (AC-2).

	Returns the ancestor chain (nearest parent first) and the direct child splits. This is
	the *split* relation only: it never reads `genealogy_links`, so a repack lineage and a
	production genealogy never conflate on the Trace Ribbon.
	"""
	ancestors: list[str] = []
	current = frappe.db.get_value("Batch", batch, PARENT_BATCH_FIELD)
	seen = {batch}
	while current and current not in seen:
		ancestors.append(current)
		seen.add(current)
		current = frappe.db.get_value("Batch", current, PARENT_BATCH_FIELD)
	children = frappe.get_all("Batch", filters={PARENT_BATCH_FIELD: batch}, pluck="name", order_by="name asc")
	return {"batch": batch, "parents": ancestors, "children": children, "is_split": bool(ancestors)}


# --------------------------------------------------------------------------------------
# Controller hooks (called from the Repacking DocType controller)
# --------------------------------------------------------------------------------------


def validate(doc: Any) -> None:
	"""`Repacking.validate` — the single funnel for the journey."""
	if not doc.get("company"):
		doc.company = frappe.db.get_value("Warehouse", doc.warehouse, "company")
	edge = journey.validate_transition(doc, JOURNEY)
	if edge and edge[1] == journey.ACCEPTED:
		assert_repack_feasible(doc)
	if edge:
		doc.flags.journey_edge = edge
		journey.append_history(doc, edge[0], edge[1], doc.get("reason"))


def on_update(doc: Any) -> None:
	"""`Repacking.on_update` — execute the repack when the journey reaches Accepted."""
	edge = doc.flags.get("journey_edge")
	if not edge:
		return
	doc.flags.journey_edge = None
	if edge[1] == journey.ACCEPTED:
		perform_repack(doc)
