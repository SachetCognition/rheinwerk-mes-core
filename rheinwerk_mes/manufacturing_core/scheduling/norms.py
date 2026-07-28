"""Loading TJ/TPZ and changeover norms off the site (W3-2 · URS-W3-006, URS-W3-007).

The pure calculators (`realization_time`, `changeover`, `sequencing`) work on plain
mappings; this module is the only place that reads them from the site, so the arithmetic
stays testable without a database.

Routing is read from the anchor: the `Work Order` operation rows when the order carries
them, otherwise the `Routing` behind its BOM. The anchor DocTypes are untouched — the norms
themselves live in the `Operation Time Norm` records owned by `rheinwerk_mes`.
"""

from __future__ import annotations

from typing import Any

import frappe

TIME_NORM_DOCTYPE = "Operation Time Norm"
CHANGEOVER_DOCTYPE = "Line Changeover Norm"

_NORM_FIELDS = (
	"name",
	"operation",
	"workstation",
	"production_line",
	"tpz_min",
	"tj_min_per_unit",
	"workstations_count",
	"tj_divisible",
	"staff_factor",
)


def _norm_mapping(row: dict[str, Any], operation: str, workstation: str | None) -> dict[str, Any]:
	return {
		"operation": operation,
		"workstation": workstation,
		"tpz_min": row.get("tpz_min") or 0,
		"tj_min_per_unit": row.get("tj_min_per_unit") or 0,
		"workstations_count": row.get("workstations_count") or 1,
		"tj_divisible": bool(row.get("tj_divisible", 1)),
		"staff_factor": row.get("staff_factor") or 1,
	}


def time_norm(
	operation: str, workstation: str | None = None, production_line: str | None = None
) -> dict[str, Any]:
	"""The most specific `Operation Time Norm` for one operation.

	Precedence: operation + work centre, then operation + line, then operation alone. A
	missing norm yields a zero norm — the order then has no realization time, which the
	board shows rather than inventing minutes.
	"""
	candidates = frappe.get_all(
		TIME_NORM_DOCTYPE,
		filters={"operation": operation},
		fields=list(_NORM_FIELDS),
		limit_page_length=0,
	)

	def score(row: dict[str, Any]) -> tuple[int, int]:
		workstation_rank = 0 if row.get("workstation") and row["workstation"] == workstation else 1
		line_rank = 0 if row.get("production_line") and row["production_line"] == production_line else 1
		return (workstation_rank, line_rank)

	usable = [
		row
		for row in candidates
		if (not row.get("workstation") or row["workstation"] == workstation)
		and (not row.get("production_line") or row["production_line"] == production_line)
	]
	if not usable:
		return _norm_mapping({}, operation, workstation)
	return _norm_mapping(sorted(usable, key=score)[0], operation, workstation)


def routed_operations(work_order: str) -> list[dict[str, Any]]:
	"""(operation, workstation) pairs of a production order, in routing order."""
	rows = frappe.get_all(
		"Work Order Operation",
		filters={"parent": work_order},
		fields=["operation", "workstation", "idx"],
		order_by="idx asc",
		limit_page_length=0,
	)
	if rows:
		return [{"operation": row["operation"], "workstation": row.get("workstation")} for row in rows]

	bom = frappe.db.get_value("Work Order", work_order, "bom_no")
	routing = frappe.db.get_value("BOM", bom, "routing") if bom else None
	if not routing:
		return []
	rows = frappe.get_all(
		"BOM Operation",
		filters={"parent": routing, "parenttype": "Routing"},
		fields=["operation", "workstation", "idx"],
		order_by="idx asc",
		limit_page_length=0,
	)
	return [{"operation": row["operation"], "workstation": row.get("workstation")} for row in rows]


def order_norms(work_order: str, production_line: str | None = None) -> list[dict[str, Any]]:
	"""TJ/TPZ norms of a production order's routing, in routing order (URS-W3-006 AC-1)."""
	return [
		time_norm(row["operation"], row.get("workstation"), production_line)
		for row in routed_operations(work_order)
	]


def changeover_norms(production_line: str | None = None) -> list[dict[str, Any]]:
	"""Changeover norms of a line plus the line-agnostic ones, oldest first.

	`sequence` carries the insertion order so `changeover.best_matching` can apply the
	legacy "newest wins" tie-break (`ChangeoverNormsSearchServiceImpl.java:61`).
	"""
	rows = frappe.get_all(
		CHANGEOVER_DOCTYPE,
		filters={"production_line": ("in", [production_line, "", None])} if production_line else {},
		fields=["name", "production_line", "from_item", "to_item", "changeover_min", "creation"],
		order_by="creation asc",
		limit_page_length=0,
	)
	return [
		{
			"name": row["name"],
			"production_line": row.get("production_line"),
			"from_item": row["from_item"],
			"to_item": row.get("to_item"),
			"changeover_min": row.get("changeover_min") or 0,
			"sequence": index,
		}
		for index, row in enumerate(rows, start=1)
	]
