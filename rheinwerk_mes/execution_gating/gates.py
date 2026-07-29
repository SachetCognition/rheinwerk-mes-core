"""Execution-gating hooks on the production-order state machine.

Gates are registered through the `rheinwerk_exec_state_gates` hook (URS-W1-001) and never
edit the state machine itself. Each gate only *judges* — it posts nothing — and refuses
through a German-first hard-gate message naming **rule**, **record** and **resolution**,
which the state machine raises as one modal.

| Gate | URS | Transition | Legacy baseline |
|---|---|---|---|
| `material_availability_gate` | URS-W1-008 | * → In Progress | `OrderStatesListenerServicePFTD.java:580` (`:129,134,633`) |

The Rheinwerk estate validates material availability at **order start**, so the gate hangs
off * → In Progress; the legacy `momentOfValidation` parameter is not carried over.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, strip_html

from rheinwerk_mes.warehouse.availability import available_qty, ledger_balance

IN_PROGRESS = "In Progress"

WORK_ORDER = "Work Order"

GATE_LOGGER = "execution_gating"


class TransitionContext(Protocol):
	"""What the state machine (URS-W1-001) hands each registered gate."""

	doc: Document
	from_state: str | None
	to_state: str

	def refuse(self, message: str) -> None:
		"""Collect a refusal message; the machine raises the collected messages as one modal."""


def hard_gate_message(rule: str, record: str, resolution: str) -> str:
	"""Compose a hard-gate refusal naming rule, record and resolution (design conformance)."""
	return "<br>".join(
		[
			_("<b>Regel:</b> {0}").format(rule),
			_("<b>Datensatz:</b> {0}").format(record),
			_("<b>Behebung:</b> {0}").format(resolution),
		]
	)


def kg(value: object | None) -> str:
	"""German-first mass rendering: decimal comma, trailing zeros trimmed, unit kg."""
	text = f"{flt(value):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


def material_availability_gate(context: TransitionContext) -> None:
	"""Starting an order requires every component to be available (URS-W1-008 · TC-W1-009).

	Availability is on-hand minus live reservations, so component quantities promised to
	another order or to a draft document are not counted (AC-3). A refusal lists every
	short component with its required, available and missing quantity (AC-1).
	"""
	if context.to_state != IN_PROGRESS:
		return
	shortfalls = component_shortfalls(context.doc)
	if not shortfalls:
		return

	lines = [
		_("{0}: benötigt {1}, verfügbar {2}, Fehlmenge {3}").format(
			row["item"], kg(row["required"]), kg(row["available"]), kg(row["shortfall"])
		)
		for row in shortfalls
	]
	_refuse(
		context,
		rule=_(
			"Auftragsstart erfordert vollständig verfügbare Komponenten (Bestand abzüglich Reservierungen)."
		),
		record=_("Auftrag {0} — Fehlmengen:<br>{1}").format(context.doc.name, "<br>".join(lines)),
		resolution=_(
			"Fehlmengen zubuchen, Reservierungen anderer Aufträge auflösen oder die Auftragsmenge anpassen."
		),
	)


def component_shortfalls(doc: Document) -> list[dict[str, object]]:
	"""Per-component shortfall list for a Work Order, in recipe order.

	The required quantity is what is still outstanding (`required_qty` minus what was already
	transferred to WIP); it is compared with the available quantity in the component's source
	warehouse. Reservations the order holds for itself are excluded from the competing
	reservations so an order never blocks on its own reservation.
	"""
	shortfalls: list[dict[str, object]] = []
	for row in doc.get("required_items") or []:
		warehouse = component_warehouse(row, doc)
		if not warehouse:
			continue
		required = Decimal(str(max(flt(row.required_qty) - flt(row.get("transferred_qty")), 0)))
		if required <= 0:
			continue
		available = available_qty(row.item_code, warehouse, exclude_voucher=(WORK_ORDER, doc.name))
		if available >= required:
			continue
		shortfalls.append(
			{
				"item": row.item_code,
				"warehouse": warehouse,
				"required": required,
				"available": available,
				"shortfall": required - available,
			}
		)
	return shortfalls


def component_warehouse(row: Document, doc: Document) -> str | None:
	"""Warehouse a component is drawn from: its own source when that holds stock, else the
	order's WIP or source warehouse."""
	candidates = [row.get("source_warehouse"), doc.get("wip_warehouse"), doc.get("source_warehouse")]
	for warehouse in candidates:
		if warehouse and ledger_balance(row.item_code, warehouse) > 0:
			return warehouse
	return next((warehouse for warehouse in candidates if warehouse), None)


def _refuse(context: TransitionContext, *, rule: str, record: str, resolution: str) -> None:
	"""Hand the hard-gate message to the state machine and log the refusal.

	Logging keeps the refusal traceable while the immutable `Execution Gate Log`
	(URS-W1-033) is still to come; that record supersedes this logger entry.
	"""
	context.refuse(hard_gate_message(rule, record, resolution))
	frappe.logger(GATE_LOGGER).info(
		{
			"gate": "material_availability_gate",
			"urs": "URS-W1-008",
			"reference_doctype": context.doc.doctype,
			"reference_name": context.doc.name,
			"from_state": context.from_state,
			"to_state": context.to_state,
			"rule": strip_html(rule),
			"detail": strip_html(f"{record} — {resolution}"),
			"refused_by": frappe.session.user,
		}
	)
