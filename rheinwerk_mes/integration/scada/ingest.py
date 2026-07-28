"""Ingestion of OPC-UA tag events into tracking events (W3-5 · URS-W3-015, URS-W3-021).

One event travels this path:

1. **resolve** the tag through the technologist's `OPC UA Tag Mapping` (URS-W3-016) into a
   work centre and an event type;
2. **match** an order that is `exec_state` In Progress at that work centre and pick the job
   card of the mapped (or the running) operation — matching is refused for any other
   `exec_state`, per `docs/design/W1-exec-state.md`;
3. **attach** the event as an `OPC UA Tracking Event` row attributed to source `OPC-UA`; a
   produced count also books output on the anchor Job Card through the W1 shop-floor API
   and reconciles genealogy through the W2 API — neither package is edited;
4. **audit** the event through the W1 execution-gate audit with the source system as actor
   (URS-W3-021);
5. anything that cannot be matched is **queued** as `Nicht zugeordnet` for planner
   disposition — never dropped (URS-W3-015 AC-2).

Attribution: the adapter acts as the `OPC-UA` service account (`contracts.SOURCE_SYSTEM_USER`)
for the whole ingestion, so both the tracking event and its audit entry name the source
system; job-card time logs are written without an `employee`, so no operator is ever
credited with machine-reported work.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.genealogy import links
from rheinwerk_mes.integration.scada import mapping
from rheinwerk_mes.integration.scada.contracts import (
	EVENT_OPERATION_START,
	EVENT_OPERATION_STOP,
	EVENT_PRODUCED_COUNT,
	SOURCE_SYSTEM,
	SOURCE_SYSTEM_USER,
	STATE_ASSIGNED,
	STATE_PROCESSED,
	STATE_UNMATCHED,
	TagEvent,
)
from rheinwerk_mes.manufacturing_core.shopfloor import job_execution

EVENT_DOCTYPE = "OPC UA Tracking Event"

IN_PROGRESS = "In Progress"

#: Gate name of the SCADA path in the `Execution Gate Log` (URS-W3-021).
GATE = "OPC-UA Ereignis"


@contextmanager
def as_source_system() -> Iterator[str]:
	"""Act as the OPC-UA service account so the audit actor is the source system.

	Falls back to the current session user when the account is absent (offline unit runs),
	because the attribution of the tracking event itself does not depend on it.
	"""
	previous = frappe.session.user
	if frappe.db.exists("User", SOURCE_SYSTEM_USER):
		frappe.set_user(SOURCE_SYSTEM_USER)
	try:
		yield frappe.session.user
	finally:
		if frappe.session.user != previous:
			frappe.set_user(previous)


def _in_progress_job_cards(work_centre: str, operation: str | None) -> list[dict[str, Any]]:
	"""Open job cards at one work centre whose order is In Progress, in routing sequence."""
	filters: dict[str, Any] = {"workstation": work_centre, "docstatus": 0}
	if operation:
		filters["operation"] = operation
	cards = frappe.get_all(
		"Job Card",
		filters=filters,
		fields=["name", "work_order", "operation"],
		order_by="sequence_id asc, creation asc",
	)
	return [
		card
		for card in cards
		if frappe.db.get_value("Work Order", card.work_order, "exec_state") == IN_PROGRESS
	]


def _cumulative_produced(job_card: str, up_to: Any) -> float:
	"""Produced quantity reported by OPC-UA on one card, by equipment time."""
	rows = frappe.get_all(
		EVENT_DOCTYPE,
		filters={
			"job_card": job_card,
			"event_type": EVENT_PRODUCED_COUNT,
			"event_state": ("in", (STATE_PROCESSED, STATE_ASSIGNED)),
			"equipment_timestamp": ("<=", up_to),
		},
		pluck="value",
	)
	return flt(sum(flt(value) for value in rows), 3)


def _operation_running(job_card: str) -> bool:
	"""True while the card has an open time log — the operation is still running."""
	card = frappe.get_doc("Job Card", job_card)
	return any(row.from_time and not row.to_time for row in card.get("time_logs") or [])


def book_output(job_card: str, work_order: str, up_to: Any) -> float:
	"""Book the machine-reported output on the anchor Job Card through the W1 API.

	The *cumulative* count is booked, not the increment, because the W1 `record_output`
	sets the card's completed quantity; genealogy is then reconciled through the W2 API, so
	the quantities the trace reads are the ones the equipment reported. Booking happens when
	the operation stops (or at once for a count that arrives late for an already stopped
	operation) — decision D4 in `docs/design/W3-scada-opcua.md`: `record_output` closes the
	running time log, so booking every single count would shred the operator's time record.
	"""
	cumulative = _cumulative_produced(job_card, up_to)
	if cumulative <= 0:
		return 0.0
	job_execution.record_output(job_card, cumulative)
	links.rebuild_links_for_work_order(work_order)
	return cumulative


def _drive_time_log(card: dict[str, Any], event_type: str) -> None:
	"""Start/stop the card's time log from the equipment's own start/stop signal.

	Only ever called for a writable card; a signal the card cannot honour (a stop without a
	running log, a start on a paused card) is not an ingestion failure — the event stays
	recorded and the refusal is carried in the audit detail.
	"""
	try:
		if event_type == EVENT_OPERATION_START:
			job_execution.start_job(card["name"])
		elif event_type == EVENT_OPERATION_STOP:
			job_execution.stop_job(card["name"])
	except frappe.ValidationError:
		frappe.clear_last_message()


def _insert_event(values: dict[str, Any]) -> Any:
	doc = frappe.get_doc({"doctype": EVENT_DOCTYPE, **values})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc


def log_event_audit(doc: Any, outcome_rule: str, detail: str) -> None:
	audit.log_transition(
		gate=GATE,
		rule=outcome_rule,
		document=doc,
		from_state=None,
		to_state=doc.event_state,
		detail=detail,
	)


def _queue_unmatched(event: TagEvent, reason: str, resolved: dict[str, Any] | None) -> Any:
	"""Persist an event that could not be attached — visible, never dropped (AC-2)."""
	doc = _insert_event(
		{
			"tag_address": event.tag_address,
			"event_type": (resolved or {}).get("event_type") or EVENT_PRODUCED_COUNT,
			"event_state": STATE_UNMATCHED,
			"source_system": SOURCE_SYSTEM,
			"equipment_timestamp": get_datetime(event.equipment_timestamp),
			"received_at": now_datetime(),
			"is_late": int(bool((event.meta or {}).get("late"))),
			"value": flt(event.value),
			"uom": (resolved or {}).get("uom"),
			"sequence": event.sequence,
			"work_centre_code": (resolved or {}).get("work_centre_code"),
			"production_line": (resolved or {}).get("production_line"),
			"work_centre": (resolved or {}).get("work_centre"),
			"unmatched_reason": reason,
		}
	)
	log_event_audit(doc, _("Ereignis ohne laufenden Auftrag wird zur Klärung vorgehalten"), reason)
	return doc


def ingest(event: TagEvent, late: bool = False) -> Any:
	"""Ingest one tag event; returns the `OPC UA Tracking Event` document.

	`late` marks a store-and-forward replay (URS-W3-017): the equipment timestamp is kept
	and the row is flagged `is_late`.
	"""
	started = time.monotonic()
	if late:
		event = TagEvent(
			tag_address=event.tag_address,
			value=event.value,
			equipment_timestamp=event.equipment_timestamp,
			sequence=event.sequence,
			meta={**(event.meta or {}), "late": True},
		)

	with as_source_system():
		resolved = mapping.mapping_for_tag(event.tag_address)
		if not resolved:
			return _queue_unmatched(
				event,
				_("Für die OPC-UA-Adresse {0} ist keine aktive Zuordnung gepflegt.").format(
					event.tag_address
				),
				None,
			)

		cards = _in_progress_job_cards(resolved["work_centre"], resolved.get("operation"))
		if not cards:
			return _queue_unmatched(
				event,
				_("Am Arbeitsplatz {0} läuft kein Auftrag im Zustand {1}.").format(
					resolved["work_centre_code"], _(IN_PROGRESS)
				),
				resolved,
			)

		card = cards[0]
		doc = _insert_event(
			{
				"tag_address": event.tag_address,
				"event_type": resolved["event_type"],
				"event_state": STATE_PROCESSED,
				"source_system": SOURCE_SYSTEM,
				"equipment_timestamp": get_datetime(event.equipment_timestamp),
				"received_at": now_datetime(),
				"is_late": int(bool(late)),
				"value": flt(event.value),
				"uom": resolved.get("uom"),
				"sequence": event.sequence,
				"work_centre_code": resolved["work_centre_code"],
				"production_line": resolved.get("production_line"),
				"work_centre": resolved["work_centre"],
				"work_order": card["work_order"],
				"operation": card["operation"],
				"job_card": card["name"],
			}
		)

		if resolved["event_type"] in (EVENT_OPERATION_START, EVENT_OPERATION_STOP):
			_drive_time_log(card, resolved["event_type"])
			if resolved["event_type"] == EVENT_OPERATION_STOP:
				book_output(card["name"], card["work_order"], doc.equipment_timestamp)
		elif late and not _operation_running(card["name"]):
			book_output(card["name"], card["work_order"], doc.equipment_timestamp)

		doc.db_set("processing_seconds", flt(time.monotonic() - started, 3), update_modified=False)
		doc.reload()
		log_event_audit(
			doc,
			_("Ereignis des Quellsystems {0} dem Arbeitsgang {1} zugeordnet").format(
				SOURCE_SYSTEM, card["operation"]
			),
			_("{0} · {1} · Auftrag {2} · Arbeitsgangkarte {3}").format(
				event.tag_address, resolved["event_type"], card["work_order"], card["name"]
			),
		)
		return doc


def events_of_order(work_order: str) -> list[dict[str, Any]]:
	"""OPC-UA tracking events of one order, oldest equipment time first."""
	return frappe.get_all(
		EVENT_DOCTYPE,
		filters={"work_order": work_order},
		fields=[
			"name",
			"tag_address",
			"event_type",
			"event_state",
			"operation",
			"job_card",
			"value",
			"uom",
			"equipment_timestamp",
			"received_at",
			"is_late",
			"sequence",
			"source_system",
			"processing_seconds",
		],
		order_by="equipment_timestamp asc, sequence asc",
	)
