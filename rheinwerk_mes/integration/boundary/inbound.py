"""Orders in — inbound demand from the group ERP (W3-3 · URS-W3-010).

One entrypoint, `process(payload)`, is used by the fixture player, by the health surface's
replay and by whatever transport W4 puts in front of the boundary. It is:

* **keyed by the external reference** — `ERP Sales Input.external_order_ref` is unique, so the
  demand a message describes exists exactly once (AC-1);
* **idempotent on redelivery** — a message whose `message_type:message_id` was seen before
  produces no second demand and is logged as a duplicate naming the external reference (AC-2);
* **all-or-nothing on rejection** — the payload is validated against the frozen contract
  schema *and* resolved against master data before anything is written, and the write itself
  runs inside a savepoint, so an unknown item leaves no partial data behind (AC-3).

Legacy precedent for the external key is Qcadoo's `externalNumber` / `externalSynchronized`
field pair (`Chem_mes@master`
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/constants/
OrderFields.java:48,88`) — dispositioned "carry" as XS-01/XS-02 in the W3-7 register. The
semantics are re-implemented here, never ported.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from rheinwerk_mes.integration.boundary import contracts, queues, schema


class Result:
	"""What processing one inbound message did — the fixture player's assertion surface."""

	def __init__(
		self,
		*,
		outcome: str,
		message: str,
		demand: str | None = None,
		reason_code: str | None = None,
		reason: str | None = None,
	) -> None:
		self.outcome = outcome
		self.message = message
		self.demand = demand
		self.reason_code = reason_code
		self.reason = reason

	@property
	def accepted(self) -> bool:
		return self.outcome == contracts.PROCESSED

	def as_dict(self) -> dict[str, Any]:
		return {
			"outcome": self.outcome,
			"message": self.message,
			"demand": self.demand,
			"reason_code": self.reason_code,
			"reason": self.reason,
		}


def process(payload: dict[str, Any], *, replay: bool = False) -> Result:
	"""Process one orders-in message; never raises for a rejected message."""
	try:
		schema.validate_message(payload)
		if payload["message_type"] != contracts.ORDERS_IN:
			raise schema.SchemaViolation(
				_("Nachrichtentyp {0} gehört nicht zum eingehenden Bedarf").format(payload["message_type"]),
				"$.message_type",
			)
	except contracts.BoundaryError as violation:
		return _reject(payload, violation)

	# Only a message that was *accepted* before is a duplicate. A message that was rejected
	# is retried on redelivery, so fixing the master data and resending works (AC-3).
	if not replay and queues.processed(contracts.ORDERS_IN, payload["message_id"]):
		name = queues.duplicate(
			payload,
			rule=_("Wiederholte Zustellung der Nachricht {0}: kein zweiter Bedarf angelegt.").format(
				payload["message_id"]
			),
		)
		return Result(
			outcome=contracts.PROCESSED,
			message=name,
			demand=payload["external_order_ref"],
			reason_code=contracts.REASON_DUPLICATE,
			reason=_("Duplikat zur externen Referenz {0}").format(payload["external_order_ref"]),
		)

	try:
		demand = _resolve(payload)
	except contracts.BoundaryError as violation:
		return _reject(payload, violation)

	savepoint = "rw_boundary_orders_in"
	frappe.db.savepoint(savepoint)
	try:
		name = _write_demand(payload, demand)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	message = queues.record(
		payload,
		message_state=contracts.PROCESSED,
		reference_doctype=contracts.DEMAND_DOCTYPE,
		reference_name=name,
		audit_rule=_("Eingehender Bedarf {0} verarbeitet (Vertrag v{1}).").format(
			payload["external_order_ref"], payload["contract_version"]
		),
	)
	return Result(outcome=contracts.PROCESSED, message=message, demand=name)


def _resolve(payload: dict[str, Any]) -> dict[str, Any]:
	"""Resolve the demand against master data before a single row is written."""
	demand = payload["demand"]
	item_code = demand["item_code"]
	if not frappe.db.exists("Item", item_code):
		raise contracts.BoundaryError(
			contracts.REASON_UNKNOWN_ITEM,
			_("Artikel {0} ist im MES nicht bekannt.").format(item_code),
			path="$.demand.item_code",
		)
	warehouse = _resolve_warehouse(demand["warehouse"])
	uom = demand["uom"]
	if not frappe.db.exists("UOM", uom):
		raise contracts.BoundaryError(
			contracts.REASON_UNKNOWN_UOM,
			_("Mengeneinheit {0} ist im MES nicht bekannt.").format(uom),
			path="$.demand.uom",
		)
	return {**demand, "warehouse": warehouse}


def _resolve_warehouse(warehouse: str) -> str:
	"""Accept the group ERP's warehouse name with or without the company suffix."""
	if frappe.db.exists("Warehouse", warehouse):
		return warehouse
	candidate = frappe.db.get_value("Warehouse", {"warehouse_name": warehouse}, "name")
	if candidate:
		return candidate
	raise contracts.BoundaryError(
		contracts.REASON_UNKNOWN_WAREHOUSE,
		_("Lager {0} ist im MES nicht bekannt.").format(warehouse),
		path="$.demand.warehouse",
	)


def _write_demand(payload: dict[str, Any], demand: dict[str, Any]) -> str:
	external_ref = payload["external_order_ref"]
	values = {
		"external_order_kind": payload.get("external_order_kind") or "sales-order",
		"source_system": payload["sender"],
		"received_at": now_datetime(),
		"message_id": payload["message_id"],
		"item_code": demand["item_code"],
		"quantity": demand["quantity"],
		"uom": demand["uom"],
		"warehouse": demand["warehouse"],
		"required_by": demand["required_by"],
		"customer_ref": demand.get("customer_ref"),
	}
	if frappe.db.exists(contracts.DEMAND_DOCTYPE, external_ref):
		doc = frappe.get_doc(contracts.DEMAND_DOCTYPE, external_ref)
		doc.update(values)
	else:
		doc = frappe.get_doc(
			{
				"doctype": contracts.DEMAND_DOCTYPE,
				"external_order_ref": external_ref,
				"demand_state": "Offen",
				**values,
			}
		)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return doc.name


def _reject(payload: dict[str, Any], violation: contracts.BoundaryError) -> Result:
	"""Put a message into the error queue with a machine-readable reason (AC-3)."""
	reason = violation.message
	if violation.path:
		reason = f"{reason} ({violation.path})"
	# The message type is the channel it arrived on, even when its own header is unusable —
	# that is what keeps an unroutable message visible in the orders-in error queue.
	stored = {**payload, "message_type": contracts.ORDERS_IN} if isinstance(payload, dict) else {}
	message = queues.record(
		stored or {"message_type": contracts.ORDERS_IN},
		message_state=contracts.REJECTED,
		reason_code=violation.reason_code,
		reason=reason,
		audit_rule=_("Eingehende Grenznachricht abgelehnt: {0}").format(violation.reason_code),
	)
	return Result(
		outcome=contracts.REJECTED,
		message=message,
		reason_code=violation.reason_code,
		reason=reason,
	)


def play_fixture(name: str) -> Result:
	"""Process a committed contract fixture by file name (TC-W3-013)."""
	return process(schema.fixture(name))
