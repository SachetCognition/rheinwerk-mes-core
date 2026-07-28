"""Expiry policy inside automatic allocation (W1-9 · URS-W1-030 AC-1, TC-W1-032).

`warehouse.disposal.allocate` implements the *disposal algorithm* (FIFO/LIFO/FEFO/LEFO) and
deliberately stays policy-free: it orders and splits whatever the ledger holds. The
estate-wide expiry policy signed off in URS-W1-030 is a **gating** concern and therefore
lives here:

* expired batches are removed from the candidate set — never picked, never silently
  issued, whatever the warehouse algorithm would have ranked first;
* if the unexpired stock cannot cover the demand the allocation is *refused* with a
  hard-gate modal (rule / record / resolution) and the refusal is logged immutably
  (URS-W1-033) — the caller does not receive a partial allocation it might post anyway;
* every candidate carries a signal state so the Desk and Terminal screens can flag stock
  that already expired (red) or expires within `EXPIRING_SOON_DAYS` (amber).

This is the *allocation* half of the policy; `expiry.py` is the *posting* half, refusing an
expired batch that reached a Stock Entry by any other route. Both refuse; neither weakens a
substrate rule. The divergence from Plant A's FEFO-advisory behaviour (Qcadoo orders by
expiry but issues expired resources — `ResourceManagementServiceImpl.java:1015-1027`) is
recorded in `docs/decisions/DEC-W1-030-expiry-policy.md` and proven by the
`CHAR-EXPIRY-ISSUE-01` contract.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, nowdate

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.execution_gating.expiry import OUTWARD_PURPOSES
from rheinwerk_mes.warehouse.contracts import picking_order
from rheinwerk_mes.warehouse.disposal import resources_for_warehouse, warehouse_algorithm

GATE = "expiry_allocation_gate"

#: A batch expiring within this many days is flagged amber (design tokens — signal states).
EXPIRING_SOON_DAYS = 30

#: Signal states used by the shop-floor screens.
SIGNAL_EXPIRED = "red"
SIGNAL_EXPIRING = "amber"
SIGNAL_OK = "neutral"


def batch_expiry(batch: str) -> date | None:
	expiry = frappe.db.get_value("Batch", batch, "expiry_date")
	return getdate(expiry) if expiry else None


def expiry_signal(expiry: date | None, on_date: date) -> str:
	"""Signal state of a batch: red once expired, amber shortly before, else neutral."""
	if expiry is None:
		return SIGNAL_OK
	if expiry < on_date:
		return SIGNAL_EXPIRED
	return SIGNAL_EXPIRING if (expiry - on_date).days <= EXPIRING_SOON_DAYS else SIGNAL_OK


def candidates(item: str, warehouse: str, posting_date: str | date | None = None) -> list[dict[str, Any]]:
	"""Ledger-backed resources for `item`, each annotated with its expiry signal state.

	Ordered by the warehouse's disposal algorithm, so the first entry is the batch the
	algorithm selects first — expired entries included, because the callers that render
	stock still have to *show* them (flagged red); only allocation excludes them.
	"""
	on_date = getdate(posting_date or nowdate())
	resources = {row["batch"]: row for row in resources_for_warehouse(item, warehouse)}
	ordered = picking_order(list(resources.values()), warehouse_algorithm(warehouse))
	annotated: list[dict[str, Any]] = []
	for batch in ordered:
		expiry = batch_expiry(batch)
		signal = expiry_signal(expiry, on_date)
		annotated.append(
			{
				**resources[batch],
				"expiry_date": expiry,
				"signal": signal,
				"expired": signal == SIGNAL_EXPIRED,
			}
		)
	return annotated


def allocate_under_expiry_policy(
	item: str,
	warehouse: str,
	qty: float | Decimal,
	posting_date: str | date | None = None,
) -> list[tuple[str, Decimal]]:
	"""Allocate `qty` skipping expired batches; refuse when unexpired stock is short.

	URS-W1-030 AC-1 · TC-W1-032. Returns `(batch, quantity)` pairs in disposal order.
	"""
	demand = Decimal(str(qty))
	remaining = demand
	allocations: list[tuple[str, Decimal]] = []
	rows = candidates(item, warehouse, posting_date)
	for row in rows:
		if remaining <= 0:
			break
		if row["expired"]:
			continue
		take = min(remaining, Decimal(str(row["available_quantity"])))
		if take > 0:
			allocations.append((row["batch"], take))
			remaining -= take
	if remaining > 0:
		_refuse_shortfall(item, warehouse, demand, remaining, rows, getdate(posting_date or nowdate()))
	return allocations


def allocation_view(
	item: str,
	warehouse: str,
	qty: float | Decimal,
	posting_date: str | date | None = None,
) -> dict[str, Any]:
	"""Screen payload: the candidate list with signal states plus the unexpired coverage.

	Unlike `allocate_under_expiry_policy` this never throws — the planner screens need to
	*show* that only expired stock is left before the operator triggers a posting.
	"""
	on_date = getdate(posting_date or nowdate())
	rows = candidates(item, warehouse, posting_date)
	unexpired = sum(
		(Decimal(str(row["available_quantity"])) for row in rows if not row["expired"]), Decimal("0")
	)
	demand = Decimal(str(qty))
	return {
		"item": item,
		"warehouse": warehouse,
		"algorithm": warehouse_algorithm(warehouse),
		"posting_date": formatdate(on_date, "dd.MM.yyyy"),
		"required_qty": demand,
		"unexpired_qty": unexpired,
		"covered": unexpired >= demand,
		"resources": rows,
	}


def allocate_stock_entry_batches(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.validate` — fill each outward row's batch under the expiry policy.

	This is where the policy meets the real posting path: a row that draws a batched item
	without naming a batch is auto-allocated here, in the warehouse's disposal order and
	*never* from expired stock (URS-W1-030 AC-1). A row the user filled in by hand is left
	untouched — `expiry.enforce_batch_expiry` refuses it if it names an expired batch, so
	both routes end in a refusal rather than a silent issue.

	Splitting one row across several batches is not attempted: the anchor's own bundle is
	the mechanism for that, so when the allocation needs more than one batch the row is left
	for the operator (or the bundle) to resolve while the shortfall refusal above still
	fires when only expired stock remains.
	"""
	if doc.get("purpose") and doc.purpose not in OUTWARD_PURPOSES:
		return
	posting_date = doc.get("posting_date") or nowdate()
	for row in doc.get("items") or []:
		if not row.get("s_warehouse") or row.get("batch_no") or row.get("serial_and_batch_bundle"):
			continue
		if not frappe.db.get_value("Item", row.item_code, "has_batch_no"):
			continue
		allocated = allocate_under_expiry_policy(
			row.item_code, row.s_warehouse, row.get("qty") or 0, posting_date
		)
		if len(allocated) == 1:
			row.batch_no = allocated[0][0]


def _refuse_shortfall(
	item: str,
	warehouse: str,
	demand: Decimal,
	shortfall: Decimal,
	rows: list[dict[str, Any]],
	on_date: date,
) -> None:
	expired = [row for row in rows if row["expired"]]
	rule = _(
		"Verfallene Chargen werden nicht zugeteilt; ohne ausreichenden nicht verfallenen "
		"Bestand wird die Entnahme abgelehnt (Sperrregel, estate-weit)."
	)
	record = "<br>".join(
		[
			_("Artikel {0}, Lager {1} — Bedarf {2} kg, Fehlmenge {3} kg zum {4}").format(
				item, warehouse, demand, shortfall, formatdate(on_date, "dd.MM.yyyy")
			),
			*[
				_("Charge {0} übersprungen — verfallen am {1}, Restmenge {2} kg").format(
					row["batch"],
					formatdate(row["expiry_date"], "dd.MM.yyyy"),
					row["available_quantity"],
				)
				for row in expired
			],
		]
	)
	resolution = _(
		"Nicht verfallenen Bestand beschaffen oder eine QA-Verwendungsentscheidung für die "
		"verfallene Charge einholen."
	)
	audit.log_refusal(
		gate=GATE,
		rule=rule,
		document=frappe._dict(doctype="Item", name=item),
		detail=_(
			"Zuteilung {0} kg {1} aus {2} abgelehnt: Fehlmenge {3} kg nach Ausschluss verfallener Chargen."
		).format(demand, item, warehouse, shortfall),
	)
	frappe.throw(
		"<br>".join(
			[
				_("<b>Regel:</b> {0}").format(rule),
				_("<b>Datensatz:</b> {0}").format(record),
				_("<b>Behebung:</b> {0}").format(resolution),
			]
		),
		title=_("Entnahme abgelehnt: nur verfallener Bestand verfügbar"),
	)
