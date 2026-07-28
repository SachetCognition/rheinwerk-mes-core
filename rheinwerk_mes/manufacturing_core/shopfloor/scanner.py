"""Scanner-first identification on shop-floor screens (W1-7 · URS-W1-028, URS-W1-032).

Every screen that expects an order, material or batch identification carries one
always-focused scan field (design skill § "Interaction rules — Scanner is a first-class
input"). The client keeps focus and plays the confirmation; the server resolves the code
and always answers — a *recognised* payload with the full-row highlight target, or a
non-blocking inline error naming the unrecognised code. Gated actions are never
optimistically confirmed (URS-W1-032), so the resolution is a server round trip.
"""

from __future__ import annotations

import time
from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.manufacturing_core.shopfloor.formatting import format_date_de, format_kg
from rheinwerk_mes.manufacturing_core.shopfloor.terminal import state_pill

WORK_ORDER = "work_order"
JOB_CARD = "job_card"
BATCH = "batch"
ITEM = "item"

#: Resolution order — the first anchor DocType whose name matches wins.
SCAN_TARGETS: tuple[tuple[str, str], ...] = (
	(WORK_ORDER, "Work Order"),
	(JOB_CARD, "Job Card"),
	(BATCH, "Batch"),
	(ITEM, "Item"),
)


def _payload(kind: str, doctype: str, name: str) -> dict[str, Any]:
	"""The recognised-scan payload the terminal highlights and reads aloud."""
	doc = frappe.get_doc(doctype, name)
	payload: dict[str, Any] = {
		"recognised": True,
		"kind": kind,
		"doctype": doctype,
		"name": name,
		"highlight": f"{kind}:{name}",
		"confirm_sound": "scan-ok",
	}
	if kind == WORK_ORDER:
		payload |= {
			"label": _("Fertigungsauftrag {0}").format(name),
			"exec_state": doc.get("exec_state"),
			"status_pill": state_pill(doc.get("exec_state")),
			"qty_display": format_kg(doc.qty),
		}
	elif kind == JOB_CARD:
		payload |= {
			"label": _("Arbeitsgang {0} ({1})").format(doc.operation, name),
			"work_order": doc.work_order,
			"status_pill": state_pill(doc.status),
		}
	elif kind == BATCH:
		payload |= {
			"label": _("Charge {0}").format(name),
			"item_code": doc.item,
			"expiry_display": format_date_de(doc.get("expiry_date")),
		}
	else:
		payload |= {"label": _("Material {0}").format(name), "item_name": doc.item_name}
	return payload


def resolve(code: str) -> dict[str, Any]:
	"""Resolve one scanned code; never raises — an unknown code is a payload, not an error."""
	scanned = (code or "").strip()
	# An empty scan is a hardware hiccup, not an operator error: keep the field focused.
	if not scanned:
		return {
			"recognised": False,
			"code": scanned,
			"keep_focus": True,
			"message": _("Leerer Scan — bitte erneut scannen."),
		}
	for kind, doctype in SCAN_TARGETS:
		if not frappe.db.exists(doctype, scanned):
			continue
		# A code the scanning user may not read is reported as unknown rather than refused:
		# the terminal must not become a way to enumerate orders, batches or materials.
		if not frappe.has_permission(doctype, "read", doc=scanned):
			break
		return _payload(kind, doctype, scanned)
	return {
		"recognised": False,
		"code": scanned,
		"keep_focus": True,
		"message": _("Barcode {0} ist nicht bekannt.").format(scanned),
	}


@frappe.whitelist()
def scan(code: str) -> dict[str, Any]:
	"""Whitelisted scan entrypoint; reports its own server time for the latency budget.

	`server_ms` is what URS-W1-032 measures (p95 ≤ 300 ms server-confirmed); the client
	renders its feedback within 100 ms and waits for this confirmation before showing any
	gated action as done.
	"""
	started = time.perf_counter()
	result = resolve(code)
	result["server_ms"] = round((time.perf_counter() - started) * 1000, 3)
	return result
