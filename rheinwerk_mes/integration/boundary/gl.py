"""GL postings out — boundary costing/valuation (W3-4 · URS-W3-012).

The substrate keeps perpetual inventory: every posted stock movement produces a stock ledger
entry with a `stock_value_difference`, and ERPNext would normally book that into its own GL.
Per ADR-002 the MES holds **no financial ledger of record**, so the value movement is mapped
onto group-ERP account codes through `Group ERP Account Map` and emitted across the boundary
as a balanced debit/credit pair.

The map is the whole safety mechanism (AC-2): a warehouse without a map entry does not get a
guessed account. Its posting is stored in the hold queue with reason `UNMAPPED_WAREHOUSE`, an
alert naming the warehouse and the missing map entry is raised, and **nothing is emitted** —
`transport().send` is never reached for that posting.

Evidence for the substrate behaviour being fenced out here: dossier ch. 3.2
`erpnext/controllers/stock_controller.py` (perpetual-inventory GL from SLE),
`erpnext/stock/doctype/item/item.json:387-390` (valuation methods).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate

from rheinwerk_mes.integration.boundary import contracts, outbound, queues

DEFAULT_CURRENCY = "EUR"

#: Ledger entries below this absolute value produce no boundary posting (rounding noise).
VALUE_EPSILON = 0.005


def account_map(warehouse: str) -> dict[str, Any] | None:
	"""The group-ERP account map entry of a warehouse, or `None` when unmapped."""
	if not frappe.db.exists(contracts.ACCOUNT_MAP_DOCTYPE, warehouse):
		return None
	return frappe.db.get_value(
		contracts.ACCOUNT_MAP_DOCTYPE,
		warehouse,
		["warehouse", "stock_account_code", "offset_account_code", "currency"],
		as_dict=True,
	)


def ledger_entries(voucher_type: str, voucher_no: str) -> list[dict[str, Any]]:
	"""The value-bearing stock ledger entries of one voucher, in posting order."""
	return frappe.get_all(
		"Stock Ledger Entry",
		filters={"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0},
		fields=[
			"name",
			"item_code",
			"warehouse",
			"batch_no",
			"actual_qty",
			"stock_uom",
			"posting_date",
			"stock_value_difference",
		],
		order_by="creation asc",
		limit_page_length=0,
	)


def message_id(entry_name: str) -> str:
	"""Message id of a posting: the ledger entry is the natural once-only key."""
	return f"GL-{entry_name}".upper()


def build_posting(entry: dict[str, Any], voucher_type: str, voucher_no: str) -> dict[str, Any]:
	"""The contract payload for one stock ledger entry, mapped or not.

	An unmapped warehouse yields a payload with empty account codes on purpose: it is stored
	as the evidence of what was withheld and is refused by the contract schema, which is the
	machine-checkable proof that a wrong posting cannot leave the MES.
	"""
	mapping = account_map(entry["warehouse"]) or {}
	value = flt(entry["stock_value_difference"])
	stock_account = mapping.get("stock_account_code") or ""
	offset_account = mapping.get("offset_account_code") or ""
	amount = abs(value)
	inbound_movement = value > 0
	stock_line = {
		"account": stock_account,
		"debit": amount if inbound_movement else 0.0,
		"credit": 0.0 if inbound_movement else amount,
		"description": _("Bestandswertänderung {0}").format(entry["warehouse"]),
	}
	offset_line = {
		"account": offset_account,
		"debit": 0.0 if inbound_movement else amount,
		"credit": amount if inbound_movement else 0.0,
		"description": _("Gegenbuchung Bestandsveränderung"),
	}
	return {
		"contract_version": contracts.CONTRACT_VERSION,
		"message_type": contracts.GL_POSTING_OUT,
		"message_id": message_id(entry["name"]),
		"sender": outbound.SENDER,
		"posting_date": getdate(entry["posting_date"]).isoformat(),
		"voucher": {
			"doctype": voucher_type,
			"name": voucher_no,
			"stock_ledger_entry": entry["name"],
		},
		"warehouse": entry["warehouse"],
		"item_code": entry["item_code"],
		"batch_no": entry.get("batch_no"),
		"quantity": flt(entry["actual_qty"]),
		"uom": entry.get("stock_uom") or "Kg",
		"currency": mapping.get("currency") or DEFAULT_CURRENCY,
		"lines": [stock_line, offset_line],
	}


def emit_for_voucher(voucher_type: str, voucher_no: str) -> dict[str, list[str]]:
	"""Emit (or hold) a boundary GL posting per value-bearing ledger entry of a voucher."""
	emitted: list[str] = []
	held: list[str] = []
	for entry in ledger_entries(voucher_type, voucher_no):
		if abs(flt(entry["stock_value_difference"])) < VALUE_EPSILON:
			continue
		payload = build_posting(entry, voucher_type, voucher_no)
		if account_map(entry["warehouse"]) is None:
			held.append(hold(payload, entry["warehouse"]))
			continue
		emitted.append(
			outbound.emit(
				payload,
				reference_doctype=voucher_type,
				reference_name=voucher_no,
				warehouse=entry["warehouse"],
			)
		)
	return {"emitted": emitted, "held": held}


def hold(payload: dict[str, Any], warehouse: str) -> str:
	"""Hold an unmappable posting and alert, naming warehouse and missing map entry (AC-2)."""
	reason = _(
		"Lager {warehouse} hat keinen Eintrag in {doctype}; Buchung über {amount} wird "
		"zurückgehalten, bis Bestands- und Gegenkonto hinterlegt sind."
	).format(
		warehouse=warehouse,
		doctype=_(contracts.ACCOUNT_MAP_DOCTYPE),
		amount=fmt_money(_posting_amount(payload), currency=payload.get("currency") or DEFAULT_CURRENCY),
	)
	name = queues.record(
		payload,
		message_state=contracts.HELD,
		reason_code=contracts.REASON_UNMAPPED_WAREHOUSE,
		reason=reason,
		reference_doctype=payload["voucher"]["doctype"],
		reference_name=payload["voucher"]["name"],
		warehouse=warehouse,
		gate=contracts.GATE_OUTBOUND,
		audit_rule=_("Buchung ohne Kontenzuordnung zurückgehalten — nichts emittiert."),
	)
	alert(warehouse, reason)
	return name


def _posting_amount(payload: dict[str, Any]) -> float:
	return max(flt(line["debit"]) + flt(line["credit"]) for line in payload["lines"])


def alert(warehouse: str, reason: str) -> None:
	"""Raise the unmapped-warehouse alert on the planner's desk without failing the posting."""
	frappe.publish_realtime(
		"rw_boundary_unmapped_warehouse",
		{"warehouse": warehouse, "message": reason},
		user=frappe.session.user,
	)
	frappe.log_error(message=reason, title=_("Buchung ohne Kontenzuordnung zurückgehalten"))


def on_stock_entry_submit(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.on_submit` — the stock-ledger hook that feeds the boundary (URS-W3-012)."""
	emit_for_voucher(doc.doctype, doc.name)


def release_held(warehouse: str) -> dict[str, int]:
	"""Re-attempt every held posting of a warehouse once its map entry exists."""
	released = 0
	still_held = 0
	for row in queues.messages(statuses=(contracts.HELD,), message_type=contracts.GL_POSTING_OUT):
		if row["warehouse"] != warehouse:
			continue
		if release(row["name"]):
			released += 1
		else:
			still_held += 1
	return {"released": released, "held": still_held}


def release(name: str) -> bool:
	"""Re-attempt one held posting; True when it left the hold queue.

	Replay is per message (URS-W3-014 AC-3): releasing the posting an operator selected must
	not silently push the other held postings of its warehouse across the boundary as well.
	"""
	payload = queues.payload_of(name)
	warehouse = payload.get("warehouse") or frappe.db.get_value(contracts.MESSAGE_DOCTYPE, name, "warehouse")
	mapping = account_map(warehouse)
	if mapping is None:
		return False
	outbound.emit(
		_remap(payload, mapping),
		reference_doctype=payload["voucher"]["doctype"],
		reference_name=payload["voucher"]["name"],
		warehouse=warehouse,
	)
	return True


def _remap(payload: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
	"""Fill a held posting's empty account codes from the now-existing map entry."""
	stock_line, offset_line = payload["lines"][0], payload["lines"][1]
	stock_line = {**stock_line, "account": mapping["stock_account_code"]}
	offset_line = {**offset_line, "account": mapping["offset_account_code"]}
	return {
		**payload,
		"currency": mapping.get("currency") or payload.get("currency") or DEFAULT_CURRENCY,
		"lines": [stock_line, offset_line],
	}
