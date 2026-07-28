"""The one durable message store behind every boundary queue (W3-3 · URS-W3-011…014).

`Boundary Message` rows are the error queue, the unmapped-accounts hold queue, the outbound
outbox and the idempotency ledger at once — one row per contract message, keyed by
`message_type:message_id`. Keeping them in a single table is what lets the health surface
answer "how many messages need attention" and "what is the oldest unprocessed one" with one
query, and what makes replay uniform (URS-W3-014).

Every write here also writes the W1 gate audit (`execution_gating.audit`), because
URS-W3-021 requires an immutable record of every boundary message processed, rejected or
replayed — actor or source system, timestamp, action, record reference, outcome.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.integration.boundary import contracts


def idempotency_key(message_type: str, message_id: str) -> str:
	return f"{message_type}:{message_id}"


def existing(message_type: str, message_id: str) -> str | None:
	"""Name of the stored message with this type/id, if it was seen before."""
	return frappe.db.get_value(
		contracts.MESSAGE_DOCTYPE,
		{"idempotency_key": idempotency_key(message_type, message_id)},
		"name",
	)


def processed(message_type: str, message_id: str) -> str | None:
	"""Name of the message with this type/id, if it was already processed successfully."""
	name = existing(message_type, message_id)
	if not name:
		return None
	state = frappe.db.get_value(contracts.MESSAGE_DOCTYPE, name, "message_state")
	return name if state in (contracts.PROCESSED, contracts.DELIVERED) else None


def record(
	payload: dict[str, Any],
	*,
	message_state: str,
	reason_code: str | None = None,
	reason: str | None = None,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	warehouse: str | None = None,
	receipt: str | None = None,
	audit_rule: str | None = None,
	gate: str | None = None,
) -> str:
	"""Store (or update) a boundary message and audit the outcome; returns its name.

	The state transition is idempotent per message: a redelivery updates the attempt
	counter and the reason of the existing row instead of creating a second one, which is
	how "no duplicate demand" (URS-W3-010 AC-2) and "no duplicate delivery"
	(URS-W3-011 AC-2) are both guaranteed by construction.
	"""
	message_type = payload["message_type"]
	message_id = payload.get("message_id") or synthetic_id(payload)
	name = existing(message_type, message_id)
	values = {
		"message_state": message_state,
		"reason_code": reason_code,
		"reason": reason,
		"last_attempt": now_datetime(),
		# The stored payload is always the message as last seen, so a corrected or remapped
		# message is the one that gets delivered on replay — never the stale first version.
		"payload": json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
	}
	if message_state == contracts.DELIVERED:
		values["delivered_at"] = now_datetime()
		values["receipt"] = receipt

	if name:
		doc = frappe.get_doc(contracts.MESSAGE_DOCTYPE, name)
		doc.attempts = (doc.attempts or 0) + 1
		doc.update(values)
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": contracts.MESSAGE_DOCTYPE,
				"idempotency_key": idempotency_key(message_type, message_id),
				"message_id": message_id,
				"message_type": message_type,
				"direction": contracts.DIRECTIONS.get(message_type, contracts.INBOUND),
				"contract_version": payload.get("contract_version") or contracts.CONTRACT_VERSION,
				"external_reference": external_reference(payload),
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"warehouse": warehouse,
				"payload": json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
				"attempts": 1,
				"first_seen": now_datetime(),
				**values,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

	_audit(
		doc, message_state=message_state, reason=reason, reason_code=reason_code, rule=audit_rule, gate=gate
	)
	return doc.name


def synthetic_id(payload: dict[str, Any]) -> str:
	"""Stable id for a message too malformed to carry one, so it is still queueable once."""
	digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
	return f"UNROUTABLE-{digest[:16].upper()}"


def external_reference(payload: dict[str, Any]) -> str | None:
	"""The business reference a message is recognised by on the health surface."""
	for field in ("external_order_ref", "production_order"):
		if payload.get(field):
			return str(payload[field])
	voucher = payload.get("voucher") or {}
	return voucher.get("name")


def _audit(
	doc: Any,
	*,
	message_state: str,
	reason: str | None,
	reason_code: str | None,
	rule: str | None,
	gate: str | None,
) -> None:
	gate_name = gate or (
		contracts.GATE_INBOUND if doc.direction == contracts.INBOUND else contracts.GATE_OUTBOUND
	)
	detail = " · ".join(part for part in (reason_code, reason) if part) or None
	rule_text = rule or _("Grenznachricht {0} verarbeitet.").format(doc.message_type)
	if message_state in contracts.ATTENTION_STATUSES:
		audit.log_refusal(
			gate=gate_name,
			rule=rule_text,
			document=doc,
			from_state=None,
			to_state=message_state,
			detail=detail,
		)
	else:
		audit.log_transition(
			gate=gate_name,
			rule=rule_text,
			document=doc,
			from_state=None,
			to_state=message_state,
			detail=detail,
		)


def duplicate(payload: dict[str, Any], *, rule: str, gate: str | None = None) -> str:
	"""Log a redelivered message as a duplicate without changing what it produced."""
	message_type = payload.get("message_type") or ""
	message_id = payload.get("message_id") or ""
	name = existing(message_type, message_id)
	if not name:
		raise ValueError("duplicate() called for a message that was never stored")
	doc = frappe.get_doc(contracts.MESSAGE_DOCTYPE, name)
	doc.attempts = (doc.attempts or 0) + 1
	doc.last_attempt = now_datetime()
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	audit.log_refusal(
		gate=gate or contracts.GATE_INBOUND,
		rule=rule,
		document=doc,
		to_state=doc.message_state,
		detail=" · ".join(
			part
			for part in (
				contracts.REASON_DUPLICATE,
				_("Referenz {0}").format(doc.external_reference or doc.message_id),
			)
			if part
		),
	)
	return doc.name


def payload_of(name: str) -> dict[str, Any]:
	"""The stored contract payload of a message."""
	raw = frappe.db.get_value(contracts.MESSAGE_DOCTYPE, name, "payload")
	return json.loads(raw) if raw else {}


def messages(
	*,
	statuses: tuple[str, ...] | None = None,
	message_type: str | None = None,
	limit: int | None = None,
) -> list[dict[str, Any]]:
	"""Stored messages, newest first — the backing query of every queue view."""
	filters: dict[str, Any] = {}
	if statuses:
		filters["message_state"] = ["in", list(statuses)]
	if message_type:
		filters["message_type"] = message_type
	return frappe.get_all(
		contracts.MESSAGE_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"message_id",
			"message_type",
			"direction",
			"message_state",
			"contract_version",
			"external_reference",
			"warehouse",
			"reason_code",
			"reason",
			"attempts",
			"first_seen",
			"last_attempt",
			"delivered_at",
		],
		order_by="first_seen desc, creation desc",
		limit_page_length=limit or 0,
	)
