"""Trace Ribbon view model (W2-1 · URS-W2-003).

The ribbon is the programme's signature element (design skill, layout pattern 4): supplier
batches flow in from the left, the batch in focus sits centred, downstream products flow
out to the right. This module builds the *server* model the Desk page renders and the CoA
child (W2-5) embeds, so both surfaces show an identical node/state set at the same instant
(URS-W2-018 AC-1) and the print rendering is structurally the same object.

Every node carries a status pill as **icon + label + colour** — colour is never the only
signal (design skill component rules, TC-W2-005): a blocked branch is `--rw-signal-red`
*and* carries the "Gesperrt" label, an incomplete trace is amber *and* labelled
"Spur unvollständig".
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.genealogy import qa_state, trace

#: Design-token pill styling per `qa_state` (rheinwerk-mes-design-SKILL.md).
PILLS: dict[str, dict[str, str]] = {
	qa_state.QUARANTINED: {"tone": "amber", "token": "--rw-signal-amber", "icon": "clock"},
	qa_state.RELEASED: {"tone": "green", "token": "--rw-signal-green", "icon": "check"},
	qa_state.BLOCKED: {"tone": "red", "token": "--rw-signal-red", "icon": "octagon"},
}

INCOMPLETE_PILL = {
	"tone": "amber",
	"token": "--rw-signal-amber",
	"icon": "alert-triangle",
}


def _pills(node: dict[str, Any]) -> list[dict[str, str]]:
	state = node["qa_state"]
	pills = [
		{
			"label": _(qa_state.STATE_LABELS[state]),
			"state": state,
			**PILLS[state],
		}
	]
	if node["genealogy_incomplete"]:
		label = _("Spur unvollständig")
		if node["trace_boundary_date"]:
			label = _("Spur unvollständig (Spurgrenze {0})").format(node["trace_boundary_date"])
		pills.append({"label": label, "state": "genealogy_incomplete", **INCOMPLETE_PILL})
	for ancestor in node["blocked_ancestors"]:
		pills.append(
			{
				"label": _("Gesperrter Vorgänger: {0}").format(ancestor),
				"state": "blocked_ancestor",
				**INCOMPLETE_PILL,
			}
		)
	return pills


def _chips(tree: dict[str, Any], side: str) -> list[dict[str, Any]]:
	"""Flatten one direction into ribbon chips, nearest level first."""
	chips = []
	for node in trace.flatten(tree):
		if node["level"] == 0:
			continue
		chips.append(
			{
				"batch": node["batch"],
				"item": node["item"],
				"level": node["level"],
				"side": side,
				"qty": node["qty"],
				"uom": node["uom"],
				"production_order": node["production_order"],
				"qa_state": node["qa_state"],
				"expiry_date": node["expiry_date"],
				# A blocked node breaks its branch hard (URS-W2-003 AC-2).
				"branch_break": node["qa_state"] == qa_state.BLOCKED,
				"revisited": bool(node.get("revisited")),
				"pills": _pills(node),
			}
		)
	return sorted(chips, key=lambda chip: (chip["level"], chip["batch"]))


@frappe.whitelist()
def ribbon(batch: str, levels: int = trace.MAX_LEVELS) -> dict[str, Any]:
	"""Ribbon model for `batch`: `left` (suppliers), `focus`, `right` (downstream)."""
	levels = int(levels)
	backward = trace.backward(batch, levels)
	forward = trace.forward(batch, levels)
	focus = {
		"batch": backward["batch"],
		"item": backward["item"],
		"level": 0,
		"side": "focus",
		"qa_state": backward["qa_state"],
		"expiry_date": backward["expiry_date"],
		"branch_break": backward["qa_state"] == qa_state.BLOCKED,
		"pills": _pills(backward),
	}
	return {
		"focus": focus,
		"left": _chips(backward, "left"),
		"right": _chips(forward, "right"),
		"levels": levels,
		"printable": True,
	}
