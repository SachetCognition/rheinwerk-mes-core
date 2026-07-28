"""Stocktaking journey — count, difference, correcting movement (W2-8 · URS-W2-026).

A Stocktaking is a `draft → in progress → accepted` journey (or `→ rejected`) over one
warehouse. Accepting it posts, for every counted line that differs from the live ledger, a
correcting anchor Stock Entry so the ledger ends at the counted quantity — no quantity is
invented or lost, and the record then becomes immutable. The count sheet is ordered by the
warehouse's disposal algorithm, exactly the order Qcadoo lists resources for counting.

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`materialFlowResources/states/constants/StocktakingState.java` (the `StateEnum` transition
set) and `service/ResourceManagementServiceImpl.java:1015-1027` (algorithm-ordered resource
selection). Qcadoo's terminal `FINALIZED`/`FINISHED` pair is collapsed onto a single
`Accepted` per URS-W2-026 (decision recorded in `docs/design/W2-warehouse-completion.md`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from rheinwerk_mes.warehouse import journey, movements
from rheinwerk_mes.warehouse.availability import ledger_balance
from rheinwerk_mes.warehouse.disposal import picking_order_for_warehouse

WORKFLOW_NAME = "Stocktaking Journey"

#: Qcadoo `StocktakingState.canChangeTo`, with FINALIZED/FINISHED collapsed onto Accepted:
#: Draft → {In Progress, Rejected}; In Progress → {Accepted, Rejected}; both terminal.
JOURNEY = journey.Journey(
	workflow_name=WORKFLOW_NAME,
	state_field="state",
	transitions={
		journey.DRAFT: frozenset({journey.IN_PROGRESS, journey.REJECTED}),
		journey.IN_PROGRESS: frozenset({journey.ACCEPTED, journey.REJECTED}),
		journey.ACCEPTED: frozenset(),
		journey.REJECTED: frozenset(),
	},
	initial=journey.DRAFT,
	reason_required=frozenset({journey.REJECTED}),
)


def _open_states() -> frozenset[str]:
	"""Non-terminal states — an open stocktaking still holds its warehouse."""
	return frozenset(JOURNEY.transitions) - JOURNEY.terminal_states


def assert_single_open(doc: Any) -> None:
	"""Refuse a second open stocktaking for the same warehouse (URS-W2-026 AC-2)."""
	if doc.state in JOURNEY.terminal_states:
		return
	clash = frappe.get_all(
		"Stocktaking",
		filters={
			"warehouse": doc.warehouse,
			"state": ("in", sorted(_open_states())),
			"name": ("!=", doc.name or ""),
		},
		limit=1,
	)
	if clash:
		frappe.throw(
			_("Für Lager {0} ist bereits eine offene Inventur ({1}) vorhanden.").format(
				doc.warehouse, clash[0].name
			),
			title=_("Inventur abgelehnt"),
		)


def compute_differences(doc: Any) -> None:
	"""Refresh each line's difference (counted − book snapshot) before every save."""
	for line in doc.get("lines") or []:
		line.difference = flt(line.counted_qty) - flt(line.book_qty)


@frappe.whitelist()
def populate_count_sheet(stocktaking: str) -> int:
	"""Fill the count sheet from the ledger, ordered by the warehouse disposal algorithm.

	One line per `(item, batch)` with a positive ledger balance, the book quantity snapshot
	from the ledger and the counted quantity pre-set to it (the clerk overwrites what
	differs). Batches are listed in disposal order (`picking_order_for_warehouse`), the
	order Qcadoo walks resources for a count. Returns the number of lines created.
	"""
	doc = frappe.get_doc("Stocktaking", stocktaking)
	doc.set("lines", [])
	items = frappe.get_all(
		"Batch",
		filters={"disabled": 0},
		distinct=True,
		pluck="item",
	)
	seen: set[str] = set()
	for item in items:
		if not item or item in seen:
			continue
		seen.add(item)
		for batch in picking_order_for_warehouse(item, doc.warehouse):
			balance = ledger_balance(item, doc.warehouse, batch, consider_expired=True)
			if balance <= 0:
				continue
			doc.append(
				"lines",
				{
					"item": item,
					"batch_no": batch,
					"storage_location": frappe.db.get_value("Batch", batch, "storage_location"),
					"book_qty": float(balance),
					"counted_qty": float(balance),
					"uom": frappe.db.get_value("Item", item, "stock_uom"),
				},
			)
	doc.save()
	return len(doc.get("lines") or [])


def post_corrections(doc: Any) -> list[str]:
	"""Post one correcting Stock Entry per divergent line; return the entry names (AC-1).

	The correction is measured against the **live** ledger balance at acceptance, so the
	ledger ends exactly at the counted quantity — a count below book posts a Material Issue
	(Qcadoo `RELEASE`), a count above book a Material Receipt (`RECEIPT`). Lines that agree
	post nothing. The single-truth ledger stays authoritative; the stocktaking never writes
	a parallel quantity.
	"""
	posted: list[str] = []
	for line in doc.get("lines") or []:
		if not line.batch_no:
			continue
		current = ledger_balance(line.item, doc.warehouse, line.batch_no, consider_expired=True)
		correction = Decimal(str(flt(line.counted_qty))) - current
		if correction == 0:
			continue
		if correction < 0:
			entry = movements.book_movement(
				document_type="RELEASE",
				item=line.item,
				qty=float(-correction),
				batch_no=line.batch_no,
				company=doc.company,
				source_warehouse=doc.warehouse,
				storage_location=line.storage_location,
			)
		else:
			entry = movements.book_movement(
				document_type="RECEIPT",
				item=line.item,
				qty=float(correction),
				batch_no=line.batch_no,
				company=doc.company,
				target_warehouse=doc.warehouse,
				storage_location=line.storage_location,
				basic_rate=_valuation_rate(line.item, doc.warehouse, line.batch_no),
			)
		frappe.db.set_value("Stocktaking Line", line.name, "correction_stock_entry", entry)
		line.correction_stock_entry = entry
		posted.append(entry)
	return posted


def _valuation_rate(item: str, warehouse: str, batch_no: str) -> float:
	"""Last known valuation rate for the batch, so a positive correction values sanely."""
	rate = frappe.db.get_value(
		"Stock Ledger Entry",
		{"item_code": item, "warehouse": warehouse, "batch_no": batch_no, "is_cancelled": 0},
		"valuation_rate",
		order_by="posting_date desc, posting_time desc, creation desc",
	)
	if rate:
		return float(rate)
	return float(frappe.db.get_value("Item", item, "valuation_rate") or 0) or 1.0


# --------------------------------------------------------------------------------------
# Controller hooks (called from the Stocktaking DocType controller)
# --------------------------------------------------------------------------------------


def validate(doc: Any) -> None:
	"""`Stocktaking.validate` — the single funnel for the journey."""
	if not doc.get("company"):
		doc.company = frappe.db.get_value("Warehouse", doc.warehouse, "company")
	assert_single_open(doc)
	compute_differences(doc)
	edge = journey.validate_transition(doc, JOURNEY)
	if edge:
		doc.flags.journey_edge = edge
		journey.append_history(doc, edge[0], edge[1], doc.get("reason"))


def on_update(doc: Any) -> None:
	"""`Stocktaking.on_update` — post the corrections when the journey reaches Accepted."""
	edge = doc.flags.get("journey_edge")
	if not edge:
		return
	doc.flags.journey_edge = None
	if edge[1] == journey.ACCEPTED:
		post_corrections(doc)
