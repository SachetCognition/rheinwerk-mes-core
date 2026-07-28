"""Multi-level forward and backward genealogy trees (W2-1 · URS-W2-002).

`backward(batch)` answers "produced from" (down to supplier batches) and `forward(batch)`
answers "used to produce" (up to finished goods). Both return the same node shape, so the
Trace Ribbon (URS-W2-003), the CoA child (W2-5) and the W2-9 trace demonstration all
consume one structure.

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/
advancedGenealogy/listeners/AdvancedGenealogyTreeViewListeners.java:71-73` — Qcadoo
offers the two directions (`producedFrom` / `usedToProduce`) over the tracking-record
tree. Cycle safety is ours: a batch is expanded at most once per traversal, so a data
error can never make the trace loop or duplicate a node (URS-W2-002 AC-3).

Node shape::

    {
        "batch": "BATCH-A-0001",
        "item": "RW-CHM-0001",
        "level": 1,
        "qty": 480.0,               # quantity on the edge leading to this node, kg
        "uom": "Kg",
        "production_order": "PO-2026-0001",
        "qa_state": "Released",
        "qa_state_label": "Freigegeben",
        "expiry_date": "31.12.2026",
        "genealogy_incomplete": False,
        "trace_boundary_date": None,
        "blocked_ancestors": ["BATCH-A-0002"],
        "children": [ ... ],
    }
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, formatdate

from rheinwerk_mes.genealogy import links, qa_state

BACKWARD = "backward"
FORWARD = "forward"

#: Depth ceiling; a chemical genealogy is a handful of levels deep, and the ceiling keeps
#: a corrupt data set from exhausting the request (URS-W2-033 latency floor).
MAX_LEVELS = 20


def _node(batch: str, level: int, edge: dict[str, Any] | None = None) -> dict[str, Any]:
	values = (
		frappe.db.get_value(
			"Batch",
			batch,
			["item", "expiry_date", "qa_state", "genealogy_incomplete", "trace_boundary_date"],
			as_dict=True,
		)
		or frappe._dict()
	)
	state = values.get("qa_state") or qa_state.INITIAL_STATE
	return {
		"batch": batch,
		"item": values.get("item"),
		"level": level,
		"qty": flt(edge.get("qty")) if edge else None,
		"uom": edge.get("uom") if edge else None,
		"production_order": edge.get("production_order") if edge else None,
		"qa_state": state,
		"qa_state_label": qa_state.STATE_LABELS.get(state, state),
		"expiry_date": formatdate(values.get("expiry_date"), "dd.MM.yyyy")
		if values.get("expiry_date")
		else None,
		"genealogy_incomplete": bool(values.get("genealogy_incomplete")),
		"trace_boundary_date": formatdate(values.get("trace_boundary_date"), "dd.MM.yyyy")
		if values.get("trace_boundary_date")
		else None,
		"blocked_ancestors": blocked_ancestors(batch),
		"children": [],
	}


def blocked_ancestors(batch: str) -> list[str]:
	"""Advisory ancestors currently recorded on `batch` (URS-W2-009)."""
	if not frappe.get_meta("Batch").get_field("blocked_ancestors"):
		return []
	return frappe.get_all(
		"Blocked Ancestor Advisory",
		filters={"parent": batch, "parenttype": "Batch"},
		pluck="ancestor_batch",
		order_by="ancestor_batch asc",
	)


def _edges(batch: str, direction: str) -> list[dict[str, Any]]:
	if direction == BACKWARD:
		return [
			{
				"batch": row["batch"],
				"qty": row["qty"],
				"uom": row["uom"],
				"production_order": row["production_order"],
			}
			for row in links.links_of(batch, links.CONSUMED)
		]
	return [
		{
			"batch": row["produced_batch"],
			"qty": row["qty"],
			"uom": row["uom"],
			"production_order": row["production_order"],
		}
		for row in links.consumers_of(batch)
	]


def _walk(batch: str, direction: str, levels: int) -> dict[str, Any]:
	root = _node(batch, 0)
	visited = {batch}
	frontier = [(root, 0)]
	while frontier:
		node, level = frontier.pop(0)
		if level >= min(levels, MAX_LEVELS):
			continue
		for edge in _edges(node["batch"], direction):
			child = _node(edge["batch"], level + 1, edge)
			node["children"].append(child)
			if edge["batch"] in visited:
				# Cycle guard: the node is shown once with its edge, never expanded twice.
				child["revisited"] = True
				continue
			visited.add(edge["batch"])
			frontier.append((child, level + 1))
	return root


@frappe.whitelist()
def backward(batch: str, levels: int = MAX_LEVELS) -> dict[str, Any]:
	""" "Produced from" tree of `batch` — supplier batches downwards (URS-W2-002 AC-1/3)."""
	return _walk(batch, BACKWARD, int(levels))


@frappe.whitelist()
def forward(batch: str, levels: int = MAX_LEVELS) -> dict[str, Any]:
	""" "Used to produce" tree of `batch` — finished-goods batches upwards (AC-2)."""
	return _walk(batch, FORWARD, int(levels))


def flatten(tree: dict[str, Any]) -> list[dict[str, Any]]:
	"""Depth-first node list of a tree — the listing form used by tests and the demo."""
	rows = [tree]
	for child in tree["children"]:
		rows.extend(flatten(child))
	return rows


def nodes_at_level(tree: dict[str, Any], level: int) -> list[dict[str, Any]]:
	return [node for node in flatten(tree) if node["level"] == level]


def descendants(batch: str) -> list[str]:
	"""Every batch downstream of `batch` at any level (blocking propagation, URS-W2-009)."""
	tree = forward(batch)
	return [node["batch"] for node in flatten(tree) if node["batch"] != batch]


def ancestors(batch: str) -> list[str]:
	"""Every batch upstream of `batch` at any level."""
	tree = backward(batch)
	return [node["batch"] for node in flatten(tree) if node["batch"] != batch]
