"""Hazmat visibility in warehouse and trace surfaces (W2-7 · URS-W2-024).

The rule the URS sets is a *density* rule, not a new screen: wherever a hazmat batch already
appears, its Lagerklasse and UN number appear with it as data — a column in the stock view,
a chip on the Trace Ribbon — and never behind progressive disclosure (design skill:
"nothing hides on desktop").

Both surfaces are produced **additively**, without touching `warehouse/**` or `genealogy/**`
(programme rule 3):

* `stock_view(item, warehouse)` reads batch balances via the documented warehouse API
  (`warehouse.availability.ledger_balance`) and the disposition via
  `genealogy.blocking`/`qa_state`, then appends the hazmat columns.
* `ribbon(batch, levels)` calls `genealogy.ribbon.ribbon` and decorates every node of the
  returned model with its hazmat chip — the sibling's model is the input, never a copy.

Both are whitelisted, so Desk views and the Terminal fetch exactly the model documented in
`docs/design/W2-hazmat.md`.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import formatdate

from rheinwerk_mes.regulatory_hazmat import profiles

#: Batch fields the stock view lists (`qa_state` is the W2-2 canonical field).
BATCH_FIELDS: tuple[str, ...] = ("name", "item", "expiry_date", "qa_state")


def _fmt_de(value: object) -> str:
	return formatdate(value, "dd.MM.yyyy") if value else ""


def _decorate(node: dict[str, Any]) -> dict[str, Any]:
	"""Attach the hazmat chip (and its two data facets) to one ribbon node."""
	chip = profiles.batch_chip(node.get("batch")) if node.get("batch") else None
	node["hazmat"] = chip
	node["hazmat_un_number"] = (chip or {}).get("un_number", "")
	node["hazmat_storage_class"] = (chip or {}).get("storage_class", "")
	if chip:
		node.setdefault("pills", []).append(
			{
				"label": chip["label"],
				"state": "hazmat",
				"tone": chip["tone"],
				"token": chip["token"],
				"icon": chip["icon"],
			}
		)
	return node


@frappe.whitelist()
def ribbon(batch: str, levels: int | None = None) -> dict[str, Any]:
	"""The W2-1 Trace Ribbon model with hazmat chips on every node (URS-W2-024 AC-1).

	Pure decoration: the node/state set is the genealogy child's, so the ribbon shows the
	same trace with or without hazmat data.
	"""
	from rheinwerk_mes.genealogy import ribbon as genealogy_ribbon

	model = (
		genealogy_ribbon.ribbon(batch, int(levels)) if levels is not None else genealogy_ribbon.ribbon(batch)
	)
	_decorate(model["focus"])
	for side in ("left", "right"):
		for node in model[side]:
			_decorate(node)
	return model


@frappe.whitelist()
def stock_view(warehouse: str, item: str | None = None) -> list[dict[str, Any]]:
	"""Warehouse stock rows with hazmat as columns (URS-W2-024 AC-1).

	One row per batch with a positive ledger balance in `warehouse` — Quarantined and
	Blocked stock included, because a stock view shows what physically stands there (the
	picking *exclusion* is a separate rule owned by `genealogy.blocking`). Every row carries
	`hazmat_un_number` and `hazmat_storage_class` as first-class columns plus the chip for
	pill rendering.
	"""
	from rheinwerk_mes.warehouse.availability import ledger_balance

	filters: dict[str, Any] = {"item": item} if item else {}
	rows: list[dict[str, Any]] = []
	for batch in frappe.get_all("Batch", filters=filters, fields=list(BATCH_FIELDS)):
		balance = ledger_balance(batch.item, warehouse, batch.name, consider_expired=True)
		if balance <= 0:
			continue
		chip = profiles.batch_chip(batch.name)
		rows.append(
			{
				"batch": batch.name,
				"item": batch.item,
				"warehouse": warehouse,
				"qty": float(balance),
				"uom": frappe.db.get_value("Item", batch.item, "stock_uom"),
				"expiry_date": _fmt_de(batch.expiry_date),
				"qa_state": batch.qa_state,
				"hazmat_un_number": (chip or {}).get("un_number", ""),
				"hazmat_storage_class": (chip or {}).get("storage_class", ""),
				"hazmat_storage_class_label": (chip or {}).get("storage_class_label", ""),
				"hazmat": chip,
			}
		)
	return sorted(rows, key=lambda row: row["batch"])


@frappe.whitelist()
def batch_hazmat(batch: str) -> dict[str, Any]:
	"""Full hazmat detail of one batch — the Batch form's hazmat panel and W3-6's entry point."""
	profile = profiles.effective_profile(batch=batch)
	return {
		"batch": batch,
		"profile": profile,
		"chip": profiles.batch_chip(batch),
		"overridden": bool(frappe.db.get_value("Batch", batch, profiles.BATCH_PROFILE_FIELD)),
	}
