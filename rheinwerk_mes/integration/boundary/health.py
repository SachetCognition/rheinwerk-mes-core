"""Interface-health surface and authorised replay (W3-3 · URS-W3-014, URS-W3-021).

Two audiences, one data set: B. Vogel (Betriebsleiter) needs a plain-language tile that says
whether the boundary is healthy, P. Krüger (IT) needs the dense queue behind it. The tile text
is deliberately a full sentence with a number — *"ERP-Nachrichten mit Handlungsbedarf: 1"* —
and it drills straight into the filtered error/hold queue.

Replay is authorised (`REPLAY_ROLES`) and always audited: actor,
timestamp, message reference and outcome land in the W1 `Execution Gate Log` through
`queues.record`, plus one explicit replay entry per invocation (URS-W3-021).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import format_datetime, time_diff_in_hours

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.integration.boundary import contracts, gl, inbound, outbound, queues

# Replay is a permission of its own (URS-W3-023 AC-2): planning a line does not authorise
# pushing a message across the boundary. P. Krüger replays in TC-W3-017 because the installer
# grants her the interface-admin role at Plant C, not because a planner may replay.
REPLAY_ROLES: tuple[str, ...] = (
	"Rheinwerk Interface Admin",
	"System Manager",
)


def metrics() -> dict[str, Any]:
	"""Counts, error-queue depth and oldest unprocessed message (AC-1)."""
	by_state: dict[str, int] = {
		status: frappe.db.count(contracts.MESSAGE_DOCTYPE, {"message_state": status})
		for status in contracts.STATUSES
	}
	by_type = {
		message_type: {
			status: frappe.db.count(
				contracts.MESSAGE_DOCTYPE, {"message_state": status, "message_type": message_type}
			)
			for status in contracts.STATUSES
		}
		for message_type in contracts.MESSAGE_TYPES
	}
	oldest = _oldest_unprocessed()
	attention = sum(by_state[status] for status in contracts.ATTENTION_STATUSES)
	return {
		"total": sum(by_state.values()),
		"by_state": by_state,
		"by_message_type": by_type,
		"error_queue_depth": by_state[contracts.REJECTED],
		"hold_queue_depth": by_state[contracts.HELD],
		"outbox_depth": by_state[contracts.QUEUED],
		"attention": attention,
		"oldest_unprocessed": oldest,
		"contract_version": contracts.CONTRACT_VERSION,
	}


def _oldest_unprocessed() -> dict[str, Any] | None:
	rows = queues.messages(statuses=contracts.OPEN_STATUSES)
	if not rows:
		return None
	oldest = min(rows, key=lambda row: row["first_seen"])
	return {
		"name": oldest["name"],
		"message_id": oldest["message_id"],
		"message_type": oldest["message_type"],
		"message_state": oldest["message_state"],
		"external_reference": oldest["external_reference"],
		"first_seen": oldest["first_seen"],
		"first_seen_display": format_datetime(oldest["first_seen"], "dd.MM.yyyy HH:mm"),
		"age_hours": round(time_diff_in_hours(None, oldest["first_seen"]), 1),
	}


def kpi_tile() -> dict[str, Any]:
	"""The plain-language tile B. Vogel reads, with the drill-down it opens (AC-2)."""
	numbers = metrics()
	attention = numbers["attention"]
	if attention:
		headline = _("ERP-Nachrichten mit Handlungsbedarf: {0}").format(attention)
		tone = "red" if numbers["error_queue_depth"] else "orange"
	else:
		headline = _("ERP-Nachrichten mit Handlungsbedarf: 0")
		tone = "green"
	return {
		"headline": headline,
		"count": attention,
		"tone": tone,
		"detail": _(
			"Fehlerwarteschlange: {errors} · Zurückgehalten: {held} · Wartend auf Zustellung: {queued}"
		).format(
			errors=numbers["error_queue_depth"],
			held=numbers["hold_queue_depth"],
			queued=numbers["outbox_depth"],
		),
		"drilldown": {
			"doctype": contracts.MESSAGE_DOCTYPE,
			"filters": {"message_state": ["in", list(contracts.ATTENTION_STATUSES)]},
		},
	}


@frappe.whitelist()
def dashboard() -> dict[str, Any]:
	"""Everything the health page renders: tile, metrics and the dense queue."""
	return {
		"tile": kpi_tile(),
		"metrics": metrics(),
		"queue": queue(),
		"labels": {
			"message_types": contracts.message_type_labels(),
			"reasons": contracts.reason_labels(),
		},
		"can_replay": can_replay(),
	}


@frappe.whitelist()
def queue(status: str | None = None, message_type: str | None = None) -> list[dict[str, Any]]:
	"""The dense queue view; unfiltered it shows everything that still needs attention."""
	statuses = (status,) if status else contracts.OPEN_STATUSES
	rows = queues.messages(statuses=statuses, message_type=message_type)
	for row in rows:
		row["first_seen_display"] = format_datetime(row["first_seen"], "dd.MM.yyyy HH:mm")
		row["last_attempt_display"] = (
			format_datetime(row["last_attempt"], "dd.MM.yyyy HH:mm") if row["last_attempt"] else ""
		)
	return rows


def can_replay(user: str | None = None) -> bool:
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles.intersection(REPLAY_ROLES))


@frappe.whitelist()
def replay(name: str) -> dict[str, Any]:
	"""Replay one stored message; authorised, audited and free of duplicate effects (AC-3)."""
	doc = frappe.get_doc(contracts.MESSAGE_DOCTYPE, name)
	_require_replay_permission(doc)
	payload = queues.payload_of(name)
	outcome = _replay_outcome(doc, payload)

	audit.log_transition(
		gate=contracts.GATE_REPLAY,
		rule=_("Grenznachricht {0} wurde durch {1} erneut verarbeitet.").format(
			doc.message_id, frappe.session.user
		),
		document=doc,
		from_state=doc.message_state,
		to_state=frappe.db.get_value(contracts.MESSAGE_DOCTYPE, name, "message_state"),
		detail=outcome["detail"],
	)
	return outcome


def _replay_outcome(doc: Any, payload: dict[str, Any]) -> dict[str, Any]:
	if doc.message_type == contracts.ORDERS_IN:
		result = inbound.process(payload, replay=True)
		return {
			"name": doc.name,
			"message_state": result.outcome,
			"detail": result.reason or _("Bedarf {0} übernommen.").format(result.demand or ""),
		}
	if doc.message_state == contracts.HELD:
		released = gl.release(doc.name)
		detail = (
			_("Buchung nach Kontenzuordnung emittiert.")
			if released
			else _("Kontenzuordnung fehlt weiterhin; Buchung bleibt zurückgehalten.")
		)
		return {
			"name": doc.name,
			"message_state": frappe.db.get_value(contracts.MESSAGE_DOCTYPE, doc.name, "message_state"),
			"detail": detail,
		}
	delivered = outbound.deliver(doc.name)
	return {
		"name": doc.name,
		"message_state": contracts.DELIVERED if delivered else contracts.QUEUED,
		"detail": _("Zugestellt.") if delivered else _("Endpunkt weiterhin nicht erreichbar."),
	}


@frappe.whitelist()
def replay_all(message_type: str | None = None) -> dict[str, int]:
	"""Replay the whole outbox after an outage (authorised, audited per message)."""
	_require_replay_permission(None)
	return outbound.flush_outbox(message_type)


def _require_replay_permission(doc: Any | None) -> None:
	"""Refuse an unauthorised replay, naming the permission it needs — and audit the refusal.

	The refusal is auditable evidence too (URS-W3-021): an attempt to push a message across the
	boundary without the replay permission is exactly what the log exists for.
	"""
	if can_replay():
		return
	rule = _("Erneutes Verarbeiten von Grenznachrichten erfordert die Rolle {0}.").format(
		", ".join(REPLAY_ROLES)
	)
	if doc is not None:
		audit.log_refusal(
			gate=contracts.GATE_REPLAY,
			rule=rule,
			document=doc,
			from_state=doc.message_state,
			to_state=doc.message_state,
			detail=_("Benutzer {0} ist nicht berechtigt.").format(frappe.session.user),
		)
	frappe.throw(rule, frappe.PermissionError)


def audit_trail(name: str) -> list[dict[str, Any]]:
	"""The full audit of one boundary message (URS-W3-021)."""
	return audit.entries_for(contracts.MESSAGE_DOCTYPE, name)
