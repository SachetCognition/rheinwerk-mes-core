"""Confirmations out — production confirmations to the group ERP (W3-3 · URS-W3-011).

The trigger is the W1 execution state machine: when a production order's `exec_state` reaches
`Completed` (see `docs/design/W1-exec-state.md` — gates judge, side effects follow the written
transition), one confirmation message is built from the order and its produced FG batches and
handed to the injected transport.

Exactly-once is a property of the store, not of the caller: the message id is derived from the
production order (`CONF-<order>`), `Completed` is terminal in `LEGAL_TRANSITIONS`, and
`queues.record` upserts on `message_type:message_id`. An unreachable endpoint therefore costs
nothing — the message stays in the durable outbox with reason `ENDPOINT_UNAVAILABLE`, shows up
in the health surface's backlog and is delivered by `flush_outbox()` on recovery, without loss
and without a second delivery (AC-2).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from rheinwerk_mes.genealogy import links
from rheinwerk_mes.integration.boundary import contracts, queues, schema, transport
from rheinwerk_mes.manufacturing_core import exec_state

SENDER = "RHEINWERK-MES"

#: Custom Field on the anchor Work Order carrying the group ERP's order reference.
EXTERNAL_REF_FIELD = "rw_external_order_ref"


def on_work_order_update(doc: Any, method: str | None = None) -> None:
	"""`Work Order.on_update(_after_submit)` — emit the confirmation of a completed order."""
	if doc.get("exec_state") != exec_state.COMPLETED:
		return
	if queues.existing(contracts.CONFIRMATION_OUT, message_id(doc.name)):
		return
	emit_confirmation(doc.name)


def message_id(work_order: str) -> str:
	return f"CONF-{work_order}"


def build_confirmation(work_order: str) -> dict[str, Any]:
	"""The contract payload for a completed production order (schema-validated by caller)."""
	order = frappe.get_doc("Work Order", work_order)
	batches = produced_batches(work_order)
	completed_at = _completed_at(order)
	payload: dict[str, Any] = {
		"contract_version": contracts.CONTRACT_VERSION,
		"message_type": contracts.CONFIRMATION_OUT,
		"message_id": message_id(work_order),
		"sender": SENDER,
		"completed_at": completed_at,
		"production_order": work_order,
		"external_order_ref": order.get(EXTERNAL_REF_FIELD) or None,
		"item_code": order.production_item,
		"produced_quantity": flt(order.produced_qty or order.qty),
		"uom": order.stock_uom,
		"batches": batches,
	}
	shortfall = _shortfall_reason(order)
	if shortfall:
		payload["shortfall_reason"] = shortfall
	return payload


def produced_batches(work_order: str) -> list[str]:
	"""FG batch identifiers the order produced, in posting order (CDM-03).

	Read through the W2 genealogy movement reader, so the confirmation names exactly the
	batches the genealogy of the order names — including the ones booked through a
	`Serial and Batch Bundle` rather than the legacy `batch_no` field.
	"""
	batches = [output["batch"] for output in links.movements_of(work_order)[links.PRODUCED]]
	if batches:
		return batches
	# No posted FG receipt (e.g. a completion recorded without a manufacture entry): fall
	# back to the batches carrying the order reference, so the confirmation still names the
	# lot the group ERP has to receive.
	return frappe.get_all(
		"Batch",
		filters={"reference_doctype": "Work Order", "reference_name": work_order},
		pluck="name",
		order_by="creation asc",
	)


def _completed_at(order: Any) -> str:
	for row in reversed(order.get("state_history") or []):
		if row.to_state == exec_state.COMPLETED and row.changed_at:
			return get_datetime(row.changed_at).isoformat(timespec="seconds")
	return now_datetime().isoformat(timespec="seconds")


def _shortfall_reason(order: Any) -> str | None:
	for row in reversed(order.get("state_history") or []):
		if row.to_state == exec_state.COMPLETED:
			return row.reason or None
	return None


def emit_confirmation(work_order: str) -> str:
	"""Build, validate, queue and try to deliver the confirmation of a completed order."""
	payload = build_confirmation(work_order)
	return emit(payload, reference_doctype="Work Order", reference_name=work_order)


def emit(
	payload: dict[str, Any],
	*,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	warehouse: str | None = None,
) -> str:
	"""Validate an outbound message, store it durably, then attempt delivery.

	Order matters: the message is queued *before* the transport is touched, so a crash or an
	unreachable endpoint can never lose it (URS-W3-011 AC-2).
	"""
	try:
		schema.validate_message(payload)
	except contracts.BoundaryError as violation:
		return queues.record(
			payload,
			message_state=contracts.REJECTED,
			reason_code=violation.reason_code,
			reason=f"{violation.message} ({violation.path})" if violation.path else violation.message,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			warehouse=warehouse,
			gate=contracts.GATE_OUTBOUND,
			audit_rule=_("Ausgehende Grenznachricht verletzt den Vertrag und wird nicht gesendet."),
		)

	name = queues.record(
		payload,
		message_state=contracts.QUEUED,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		warehouse=warehouse,
		gate=contracts.GATE_OUTBOUND,
		audit_rule=_("Ausgehende Grenznachricht {0} in die Warteschlange gestellt.").format(
			payload["message_id"]
		),
	)
	deliver(name)
	return name


def deliver(name: str) -> bool:
	"""Attempt delivery of one queued message; True when the endpoint accepted it."""
	payload = queues.payload_of(name)
	try:
		receipt = transport.transport().send(payload)
	except transport.EndpointUnavailable as unavailable:
		queues.record(
			payload,
			message_state=contracts.QUEUED,
			reason_code=unavailable.reason_code,
			reason=unavailable.message,
			gate=contracts.GATE_OUTBOUND,
			audit_rule=_("Zustellung fehlgeschlagen; Nachricht bleibt in der Warteschlange."),
		)
		return False

	queues.record(
		payload,
		message_state=contracts.DELIVERED,
		receipt=receipt,
		gate=contracts.GATE_OUTBOUND,
		audit_rule=_("Ausgehende Grenznachricht {0} zugestellt.").format(payload["message_id"]),
	)
	return True


def flush_outbox(message_type: str | None = None) -> dict[str, int]:
	"""Replay the durable outbox after an outage; returns delivered/still-queued counts."""
	delivered = 0
	pending = 0
	for row in queues.messages(statuses=(contracts.QUEUED,), message_type=message_type):
		if deliver(row["name"]):
			delivered += 1
		else:
			pending += 1
	return {"delivered": delivered, "queued": pending}
