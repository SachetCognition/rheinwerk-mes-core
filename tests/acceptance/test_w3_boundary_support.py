"""Shared helpers for the W3-3/W3-4 boundary acceptance suites (URS-W3-010…014).

Not a test module in itself. It provides the loopback transport injection every outbound case
needs, the arrangement of the seeded production orders around the `exec_state` Completed
transition, and the account-map arrangement for the GL cases — so each `test_w3_boundary_*`
module states only what its TC asserts.
"""

from __future__ import annotations

from typing import Any

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
PLANNER_USER = "p.krueger@rheinwerk-chemie.example"
OPERATOR_USER = "o.weber@rheinwerk-chemie.example"
VIEWER_USER = "b.vogel@rheinwerk-chemie.example"
EXTERNAL_REF = "GRP-SO-77001"
FG_WAREHOUSE = "FG Lager Süd - RWC"
RM_WAREHOUSE = "RM Lager Nord - RWC"
ITEM = "RW-CHM-0003"
QUANTITY = 500.0
POSTING_DATE = "2026-03-12"


def require(site: Any, doctype: str, name: str) -> Any:
	"""A programme fixture, skipping the test when the site was not seeded."""
	import pytest

	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def loopback(monkeypatch: Any) -> Any:
	"""A fresh loopback transport injected for the duration of one test."""
	from rheinwerk_mes.integration.boundary import transport

	replacement = transport.LoopbackTransport()
	monkeypatch.setattr(transport, "_override", replacement, raising=False)
	return replacement


def submitted_order(site: Any, name: str = FIRST_ORDER, external_ref: str | None = EXTERNAL_REF):
	"""The seeded order submitted (so it can be completed), linked to the group-ERP reference."""
	from rheinwerk_mes.manufacturing_core import exec_state

	doc = require(site, "Work Order", name)
	if doc.docstatus == 0:
		if not doc.get("operations"):
			doc.set_work_order_operations()
		doc.flags.ignore_permissions = True
		doc.save()
		doc.submit()
		doc.reload()
	site.db.set_value(
		"Work Order",
		doc.name,
		{"exec_state": exec_state.IN_PROGRESS, "rw_external_order_ref": external_ref},
		update_modified=False,
	)
	doc.reload()
	return doc


def book_production(site: Any, order: Any, qty: float = QUANTITY):
	"""Post the anchor's own Manufacture entry, which creates the FG batch and its ledger.

	Stock posting rights are the substrate's, so this step runs as Administrator while the
	persona-owned acts (the state transitions) stay with the personas.
	"""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	current_user = site.session.user
	site.set_user("Administrator")
	entry = site.get_doc(make_stock_entry(order.name, "Manufacture", qty))
	entry.posting_date = POSTING_DATE
	entry.posting_time = "14:00:00"
	entry.set_posting_time = 1
	entry.flags.ignore_permissions = True
	entry.save()
	entry.submit()
	site.set_user(current_user)
	order.reload()
	return entry


def complete(site: Any, order: Any):
	"""Drive the order through the W1 state machine to Completed (the W3 trigger)."""
	from rheinwerk_mes.manufacturing_core import exec_state

	order.reload()
	order.exec_state = exec_state.COMPLETED
	order.flags.ignore_permissions = True
	order.save()
	order.reload()
	return order


def clear_messages(site: Any) -> None:
	"""Empty the message store *and* its gate audit, so a case starts from a known trail.

	The audit is deliberately a separate, append-only doctype, so dropping the messages of an
	earlier run alone would leave their `Execution Gate Log` entries behind and make the trail
	of a re-created message id (`confirmation-out:CONF-PO-2026-0001`) depend on run history.
	"""
	site.db.delete("Execution Gate Log", {"reference_doctype": "Boundary Message"})
	site.db.delete("Boundary Message")


def messages(site: Any, message_type: str, **filters: Any) -> list[dict]:
	"""Stored boundary messages of one type, oldest first."""
	return site.get_all(
		"Boundary Message",
		filters={"message_type": message_type, **filters},
		fields=["name", "message_id", "message_state", "reason_code", "reason", "attempts", "warehouse"],
		order_by="creation asc",
	)
