"""Unmatched-events queue and its dispositions (W3-5 · URS-W3-015 AC-2).

An event that resolves to no In-Progress order is *held*, not dropped, and the planner
clears it here. Two dispositions exist, both audited through the W1 gate audit:

* **zuordnen** — attach the held event to an order the planner names; the event is
  re-attached to that order's job card at the mapped work centre and becomes `Zugeordnet`;
* **verwerfen** — discard it with a mandatory note (equipment test runs, cleaning cycles);
  the row survives as `Verworfen`, so nothing is ever lost.

The read model is German-first (DD.MM.YYYY HH:MM, kg) and feeds the
`scada-unmatched-events` Desk page.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from rheinwerk_mes.integration.scada import ingest
from rheinwerk_mes.integration.scada.contracts import (
	EVENT_PRODUCED_COUNT,
	STATE_ASSIGNED,
	STATE_DISCARDED,
	STATE_UNMATCHED,
)
from rheinwerk_mes.manufacturing_core.shopfloor.formatting import format_datetime_de, format_kg

EVENT_DOCTYPE = ingest.EVENT_DOCTYPE


def _row(entry: dict[str, Any]) -> dict[str, Any]:
	return {
		**entry,
		"equipment_timestamp_display": format_datetime_de(entry.get("equipment_timestamp")),
		"received_at_display": format_datetime_de(entry.get("received_at")),
		"value_display": format_kg(entry.get("value"))
		if entry.get("event_type") == EVENT_PRODUCED_COUNT
		else "",
	}


def unmatched_events(limit: int = 200) -> list[dict[str, Any]]:
	"""Held events, oldest equipment timestamp first — the planner's work queue."""
	entries = frappe.get_all(
		EVENT_DOCTYPE,
		filters={"event_state": STATE_UNMATCHED},
		fields=[
			"name",
			"tag_address",
			"event_type",
			"work_centre_code",
			"work_centre",
			"value",
			"uom",
			"equipment_timestamp",
			"received_at",
			"is_late",
			"sequence",
			"source_system",
			"unmatched_reason",
		],
		order_by="equipment_timestamp asc, sequence asc",
		limit=limit,
	)
	return [_row(entry) for entry in entries]


@frappe.whitelist()
def queue(limit: int = 200) -> dict[str, Any]:
	"""The unmatched-events queue page model (URS-W3-015 AC-2)."""
	frappe.has_permission(EVENT_DOCTYPE, "read", throw=True)
	rows = unmatched_events(int(limit))
	return {
		"rows": rows,
		"depth": len(rows),
		"headline": _("Nicht zugeordnete OPC-UA-Ereignisse: {0}").format(len(rows)),
		"empty_hint": _("Keine offenen Ereignisse — alle Anlagenmeldungen sind zugeordnet."),
	}


def _held_event(name: str) -> Any:
	doc = frappe.get_doc(EVENT_DOCTYPE, name)
	if doc.event_state != STATE_UNMATCHED:
		frappe.throw(
			_("Ereignis {0} ist bereits geklärt (Zustand {1}).").format(doc.name, doc.event_state),
			title=_("Klärung abgelehnt"),
		)
	return doc


@frappe.whitelist()
def assign_to_order(event: str, work_order: str, note: str | None = None) -> dict[str, Any]:
	"""Attach a held event to an order the planner names (URS-W3-015 AC-2)."""
	frappe.has_permission(EVENT_DOCTYPE, "write", throw=True)
	doc = _held_event(event)
	if not frappe.db.exists("Work Order", work_order):
		frappe.throw(
			_("Fertigungsauftrag {0} ist nicht bekannt.").format(work_order),
			title=_("Klärung abgelehnt"),
		)

	card = frappe.db.get_value(
		"Job Card",
		{"work_order": work_order, "workstation": doc.work_centre, "docstatus": 0},
		["name", "operation"],
		as_dict=True,
	)
	if not card:
		frappe.throw(
			_("Auftrag {0} hat keinen offenen Arbeitsgang am Arbeitsplatz {1}.").format(
				work_order, doc.work_centre_code or doc.work_centre
			),
			title=_("Klärung abgelehnt"),
		)

	doc.db_set(
		{
			"event_state": STATE_ASSIGNED,
			"work_order": work_order,
			"operation": card["operation"],
			"job_card": card["name"],
			"disposition_note": note,
			"dispositioned_by": frappe.session.user,
			"dispositioned_at": now_datetime(),
		},
		update_modified=False,
	)
	doc.reload()
	if doc.event_type == EVENT_PRODUCED_COUNT:
		ingest.book_output(card["name"], work_order, doc.equipment_timestamp)
	ingest.log_event_audit(
		doc,
		_("Nicht zugeordnetes Ereignis dem Auftrag {0} zugeordnet").format(work_order),
		_("{0} · {1} · Arbeitsgangkarte {2}").format(doc.tag_address, format_kg(doc.value), card["name"]),
	)
	return {"event": doc.name, "event_state": doc.event_state, "work_order": work_order}


@frappe.whitelist()
def discard(event: str, note: str) -> dict[str, Any]:
	"""Discard a held event with a mandatory note; the row survives as `Verworfen`."""
	frappe.has_permission(EVENT_DOCTYPE, "write", throw=True)
	doc = _held_event(event)
	if not (note or "").strip():
		frappe.throw(
			_("Das Verwerfen eines Ereignisses benötigt eine Begründung."),
			title=_("Klärung abgelehnt"),
		)
	doc.db_set(
		{
			"event_state": STATE_DISCARDED,
			"disposition_note": note,
			"dispositioned_by": frappe.session.user,
			"dispositioned_at": now_datetime(),
		},
		update_modified=False,
	)
	doc.reload()
	ingest.log_event_audit(doc, _("Nicht zugeordnetes Ereignis verworfen"), note)
	return {"event": doc.name, "event_state": doc.event_state}
