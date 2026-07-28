"""Whitelisted SCADA entry points for the Desk pages and the demo stack (W3-5).

`play_fixture` drives the committed simulator through the real adapter runtime — the same
code path a plant would take — so the demo, the screenshots and the acceptance suite all
exercise ingestion, matching and unmatched queueing identically.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.integration.scada import ingest
from rheinwerk_mes.integration.scada.adapter import ScadaAdapter, default_spool_path
from rheinwerk_mes.integration.scada.buffer import SpoolBuffer
from rheinwerk_mes.integration.scada.contracts import STATE_UNMATCHED
from rheinwerk_mes.integration.scada.transport import DEFAULT_FIXTURE, SimulatedTransport


@frappe.whitelist()
def play_fixture(path: str | None = None) -> dict[str, Any]:
	"""Publish the committed fixture script through the adapter; returns what it produced."""
	frappe.only_for(("System Manager", "Rheinwerk Planner", "Rheinwerk Technologist"))
	transport = SimulatedTransport.from_fixture(path or DEFAULT_FIXTURE)
	transport.connect()
	adapter = ScadaAdapter(transport, buffer=SpoolBuffer(default_spool_path()))
	events = adapter.pump()
	matched = [doc.name for doc in events if doc and doc.event_state != STATE_UNMATCHED]
	unmatched = [doc.name for doc in events if doc and doc.event_state == STATE_UNMATCHED]
	frappe.db.commit()
	return {
		"published": len(events),
		"matched": matched,
		"unmatched": unmatched,
		"message": _("{0} Ereignisse verarbeitet, {1} zur Klärung vorgehalten.").format(
			len(matched), len(unmatched)
		),
	}


@frappe.whitelist()
def order_events(work_order: str) -> dict[str, Any]:
	"""OPC-UA tracking events of one order — the order's machine-reported history."""
	frappe.has_permission(ingest.EVENT_DOCTYPE, "read", throw=True)
	return {"work_order": work_order, "events": ingest.events_of_order(work_order)}
