"""Dispatch label data for hazmat finished goods (W3-6 · URS-W3-018 AC-1).

The label is **derived data, never a new store**: every value comes either from the effective
hazmat profile (`profiles.effective_profile` — the W2-7 API, item profile with batch override)
or from the anchor ledger (`warehouse.availability.ledger_balance` — the single quantity
truth). Nothing is copied onto the batch, so a corrected profile immediately corrects every
label printed after it.

Rendering follows the transport document ADR 5.4.1.1.1 prescribes: UN number, proper shipping
name in upper case, class, packing group, tunnel restriction code — in that order, on one
line (`transport_document_line`) *and* as separate fields, so the same model serves the
printed label, the Terminal preview and a boundary message. German-first strings, mass in kg,
dates DD.MM.YYYY (design skill).

White space in all three legacy systems (dossier §6.3): no Qcadoo/OFBiz behaviour exists to
absorb, so there is no parity contract — design decisions are recorded in
`docs/design/W3-hazmat-dispatch.md`.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Sum
from frappe.utils import now_datetime

from rheinwerk_mes.manufacturing_core.shopfloor.formatting import format_date_de, format_kg
from rheinwerk_mes.regulatory_hazmat import contracts, profiles

TEMPLATE = "rheinwerk_mes/regulatory_hazmat/templates/dispatch_label.html"


def batch_warehouse(batch: str) -> str | None:
	"""Warehouse a batch physically stands in — the batch's own field, else its ledger.

	Where the anchor keeps a `Batch.warehouse` (receiving warehouse) it wins; otherwise the
	warehouse is read from the batch's ledger — the warehouse holding the most of it — so the
	label names the place the goods are dispatched *from*, not where they were made.
	"""
	if frappe.get_meta("Batch").has_field("warehouse"):
		warehouse = frappe.db.get_value("Batch", batch, "warehouse")
		if warehouse:
			return warehouse
	ledger = frappe.qb.DocType("Stock Ledger Entry")
	rows = (
		frappe.qb.from_(ledger)
		.select(ledger.warehouse, Sum(ledger.actual_qty).as_("qty"))
		.where((ledger.batch_no == batch) & (ledger.is_cancelled == 0))
		.groupby(ledger.warehouse)
		.orderby("qty", order=Order.desc)
		.limit(1)
	).run(as_dict=True)
	if rows:
		return rows[0].warehouse
	# Bundled postings carry the batch on the bundle, not on the ledger entry itself.
	bundled = frappe.get_all(
		"Serial and Batch Entry",
		filters={"batch_no": batch},
		fields=["parent"],
		limit=1,
	)
	if not bundled:
		return None
	return frappe.db.get_value("Serial and Batch Bundle", bundled[0].parent, "warehouse")


def _pictograms(profile_name: str | None) -> list[dict[str, str]]:
	if not profile_name:
		return []
	rows = frappe.get_all(
		"Hazmat Pictogram",
		filters={"parent": profile_name, "parenttype": profiles.PROFILE_DOCTYPE},
		fields=["pictogram", "designation"],
		order_by="idx asc",
	)
	return [
		{
			"code": row.pictogram,
			"designation": row.designation or _(contracts.GHS_PICTOGRAMS.get(row.pictogram, "")),
		}
		for row in rows
	]


def transport_document_line(profile: dict[str, Any]) -> str:
	"""The ADR 5.4.1.1.1 sequence as one line: `UN 1263, FARBE, 3, III, (D/E)`.

	Only the parts that are maintained are rendered; an incomplete profile therefore reads
	visibly short, and dispatch of it is refused by `regulatory_hazmat.dispatch`.
	"""
	parts = [
		profile.get("un_number") or "",
		contracts.shipping_name(profile.get("proper_shipping_name")),
		profile.get("adr_class") or "",
		profile.get("adr_packing_group") or "",
	]
	line = ", ".join(part for part in parts if part)
	tunnel = (profile.get("adr_tunnel_code") or "").strip()
	return f"{line}, ({tunnel})" if line and tunnel else line


def label_model(
	batch: str,
	warehouse: str | None = None,
	handling_unit: str | None = None,
	qty: float | None = None,
) -> dict[str, Any]:
	"""Dispatch label data of one FG batch (URS-W3-018 AC-1).

	`qty` overrides the net quantity for a partial dispatch (one handling unit off a larger
	batch); by default the label carries the batch's ledger balance in the dispatch
	warehouse. `complete`/`missing` carry the ADR verdict, so a preview screen can show what
	the dispatch guard will refuse *before* the goods are on the loading bay.
	"""
	profile = profiles.effective_profile(batch=batch) or {}
	batch_row = (
		frappe.db.get_value(
			"Batch",
			batch,
			["item", "expiry_date", "manufacturing_date", "qa_state"],
			as_dict=True,
		)
		or frappe._dict()
	)
	item = batch_row.get("item")
	dispatch_warehouse = warehouse or batch_warehouse(batch)
	net_qty = float(qty) if qty is not None else _net_qty(item, dispatch_warehouse, batch)
	missing = contracts.missing_adr_fields(profile)
	storage_class = profile.get("storage_class") or ""
	unit = frappe.db.get_value("Item", item, "stock_uom") if item else None
	return {
		"batch": batch,
		"item": item,
		"item_name": frappe.db.get_value("Item", item, "item_name") if item else None,
		"qa_state": batch_row.get("qa_state"),
		"warehouse": dispatch_warehouse,
		"handling_unit": handling_unit,
		"consignor": frappe.db.get_default("company") or "",
		"net_qty": net_qty,
		"net_qty_display": format_kg(net_qty),
		"uom": unit,
		"manufacturing_date": format_date_de(batch_row.get("manufacturing_date")),
		"expiry_date": format_date_de(batch_row.get("expiry_date")),
		"hazmat": profile.get("name") or None,
		"un_number": profile.get("un_number") or "",
		"proper_shipping_name": contracts.shipping_name(profile.get("proper_shipping_name")),
		"adr_class": profile.get("adr_class") or "",
		"adr_class_label": contracts.adr_class_label(profile["adr_class"])
		if profile.get("adr_class")
		else "",
		"packing_group": profile.get("adr_packing_group") or "",
		"packing_group_label": (
			contracts.packing_group_label(profile["adr_packing_group"])
			if profile.get("adr_packing_group")
			else ""
		),
		"tunnel_code": profile.get("adr_tunnel_code") or "",
		"label_numbers": profile.get("adr_label_numbers") or "",
		"storage_class": storage_class,
		"storage_class_label": contracts.storage_class_label(storage_class) if storage_class else "",
		"signal_word": profile.get("signal_word") or "",
		"water_hazard_class": profile.get("water_hazard_class") or "",
		"pictograms": _pictograms(profile.get("name")),
		"sds_reference": profile.get("sds_reference") or "",
		"sds_version": profile.get("sds_version") or "",
		"sds_revision_date": profile.get("sds_revision_date") or "",
		"transport_document_line": transport_document_line(profile),
		"chip": contracts.hazmat_chip(profile or None),
		"complete": not missing,
		"missing": list(missing),
		"missing_labels": [_(contracts.ADR_FIELD_LABELS[field]) for field in missing],
		"printed_on": format_date_de(now_datetime()),
		"printed_by": frappe.session.user,
	}


def _net_qty(item: str | None, warehouse: str | None, batch: str) -> float:
	if not item or not warehouse:
		return 0.0
	from rheinwerk_mes.warehouse.availability import ledger_balance

	return float(ledger_balance(item, warehouse, batch, consider_expired=True))


@frappe.whitelist()
def dispatch_label(
	batch: str,
	warehouse: str | None = None,
	handling_unit: str | None = None,
	qty: float | None = None,
) -> dict[str, Any]:
	"""Whitelisted label data — what the dispatch station previews and prints."""
	return label_model(batch, warehouse=warehouse, handling_unit=handling_unit, qty=qty)


@frappe.whitelist()
def dispatch_label_html(
	batch: str,
	warehouse: str | None = None,
	handling_unit: str | None = None,
	qty: float | None = None,
) -> str:
	"""The printable label: one markup for the Terminal preview and the paper label.

	Same rule as the W2-5 CoA — screen and print render the *same* template, so what the
	clerk approves on the terminal is what the drum carries.
	"""
	model = label_model(batch, warehouse=warehouse, handling_unit=handling_unit, qty=qty)
	return frappe.render_template(TEMPLATE, {"label": model})
