"""Recipe governance — `gov_state` lifecycle, locks and the anchor-facing hooks (W1-4).

Requirements: URS-W1-014 (`gov_state` workflow), URS-W1-015 (structural validators at
Checked→Accepted), URS-W1-016 (Accepted recipes immutable, versioning through Outdated),
URS-W1-017 (in-use lock). Model: CDM-04 / ADR-006 — the anchor BOM/Routing split is kept
and the *pair* is governed by the `Recipe Governance` DocType; neither anchor is forked.

Legacy baseline (semantics only, re-implemented in Python):
`SachetCognition/Chem_mes@master` ·
`mes-plugins/mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/states/
constants/TechnologyState.java:33-66` (transition set) and
`.../TechnologyService.java:159-172` (`isTechnologyUsedInActiveOrder`).

Read helper for other W1 children (e.g. order acceptance requires an Accepted recipe,
URS-W1-006)::

    from rheinwerk_mes.recipe_isa88.governance import gov_state, is_accepted

    gov_state("BOM-RW-CHM-0003-001")     # -> "Accepted" | "Draft" | … | "" when ungoverned
    is_accepted("BOM-RW-CHM-0003-001")   # -> True/False
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.recipe_isa88 import validators
from rheinwerk_mes.setup.roles import TECHNOLOGIST

GOVERNANCE_DOCTYPE = "Recipe Governance"

DRAFT = "Draft"
CHECKED = "Checked"
ACCEPTED = "Accepted"
OUTDATED = "Outdated"
DECLINED = "Declined"

STATES: tuple[str, ...] = (DRAFT, CHECKED, ACCEPTED, OUTDATED, DECLINED)

#: `TechnologyState.java:33-66` — Draft may be checked, accepted or declined; Checked may
#: be accepted, sent back to Draft (rework) or declined; Accepted may only be outdated;
#: Declined and Outdated are terminal.
TRANSITIONS: dict[str, tuple[str, ...]] = {
	DRAFT: (CHECKED, ACCEPTED, DECLINED),
	CHECKED: (ACCEPTED, DRAFT, DECLINED),
	ACCEPTED: (OUTDATED,),
	DECLINED: (),
	OUTDATED: (),
}

#: Per-transition roles (URS-W1-029): the technologist owns recipe governance.
TRANSITION_ROLES: tuple[str, ...] = (TECHNOLOGIST, "System Manager")

#: Transitions whose target requires the structural validator battery (URS-W1-015);
#: `TechnologyValidationAspect.java:72-75` runs it for Accepted and Checked.
VALIDATED_TARGETS: tuple[str, ...] = (CHECKED, ACCEPTED)

#: Transitions blocked by the in-use lock (URS-W1-017);
#: `TechnologyValidationAspect.java:135-141` (Outdated / Declined).
LOCKED_TARGETS: tuple[str, ...] = (OUTDATED, DECLINED)

#: `exec_state` values that make an order active (URS-W1-017). The Qcadoo check also
#: includes `01pending`; the URS scopes the lock to Accepted/In Progress/Interrupted, so
#: pending orders stay unlocked — recorded in `docs/design/W1-recipe-governance.md`.
ACTIVE_EXEC_STATES: tuple[str, ...] = (ACCEPTED, "In Progress", "Interrupted")

#: Anchor `Work Order.status` reflections of those states, used while `exec_state` is not
#: yet installed on a site (the state-machine sibling owns that field).
ACTIVE_ANCHOR_STATUSES: tuple[str, ...] = ("Not Started", "In Process")


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).get_field(fieldname))


# --------------------------------------------------------------------------- read helpers


def governance_name(recipe: str) -> str | None:
	"""Name of the `Recipe Governance` record covering `recipe` (a BOM), if any."""
	return frappe.db.get_value(GOVERNANCE_DOCTYPE, {"bom": recipe}, "name")


def gov_state(recipe: str) -> str:
	"""Governance state of `recipe` (a BOM name), or `""` when it is not governed.

	The gate other children use (URS-W1-006: an order may only be accepted against an
	Accepted recipe). Ungoverned recipes deliberately return the empty string rather than
	Draft, so a caller can distinguish "not governed yet" from "still in draft".
	"""
	return frappe.db.get_value(GOVERNANCE_DOCTYPE, {"bom": recipe}, "gov_state") or ""


def is_accepted(recipe: str) -> bool:
	"""True when `recipe` carries an Accepted `Recipe Governance` record."""
	return gov_state(recipe) == ACCEPTED


def can_change(current: str, target: str) -> bool:
	"""Legality of a `gov_state` transition (`TechnologyState.java:33-66`)."""
	return target in TRANSITIONS.get(current, ())


def active_orders_for_recipe(recipe: str) -> list[str]:
	"""Production orders that lock `recipe` (URS-W1-017).

	Baseline `TechnologyService.java:159-172`: the technology is looked up on orders in an
	active state. `exec_state` (CDM-02) is the canonical signal and, where installed, the
	*only* one: a Pending order must not lock (URS-W1-017, `docs/design/W1-recipe-governance.md`
	§6) even though the anchor already reports it as `Not Started`. The anchor `status`
	reflection is the fallback for sites without the extension.
	"""
	filters: dict[str, Any] = {"bom_no": recipe, "docstatus": ("<", 2)}
	if _has_field("Work Order", "exec_state"):
		filters["exec_state"] = ("in", ACTIVE_EXEC_STATES)
	else:
		filters["status"] = ("in", ACTIVE_ANCHOR_STATUSES)
	return frappe.get_all("Work Order", filters=filters, pluck="name", order_by="name")


# ------------------------------------------------------------------- snapshot for validators


def _uom_convertible(item_code: str, uom: str) -> bool:
	"""True when `uom` is usable for `item_code` (stock UoM or a declared conversion)."""
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if not uom or uom == stock_uom:
		return True
	return bool(frappe.db.exists("UOM Conversion Detail", {"parent": item_code, "uom": uom}))


def recipe_snapshot(bom: str, routing: str | None = None) -> dict[str, Any]:
	"""Build the validator snapshot for a BOM (+ its selected routing).

	Mapping (CDM-04): each routing operation becomes one operation component; BOM lines
	become its input components (attached to the operation named on the line where the
	anchor records one, otherwise to the first operation); the BOM's `uom` is the
	production unit and the output item's `stock_uom` the output unit.
	"""
	bom_doc = frappe.get_doc("BOM", bom)
	routing_name = routing or bom_doc.get("routing")
	operations = list(bom_doc.get("operations") or [])
	if not operations and routing_name and frappe.db.exists("Routing", routing_name):
		operations = list(frappe.get_doc("Routing", routing_name).get("operations") or [])

	output_unit = frappe.db.get_value("Item", bom_doc.item, "stock_uom")
	components: list[dict[str, Any]] = []
	for index, operation in enumerate(operations, start=1):
		components.append(
			{
				"node_number": str(index),
				"operation": operation.get("operation"),
				"production_in_one_cycle_unit": bom_doc.get("uom"),
				"main_output_product_unit": output_unit,
				"main_output_product": bom_doc.item,
				"next_operation_after_produced_type": "01all",
				"operation_product_in_components": [],
			}
		)

	for row in bom_doc.get("items") or []:
		target = components[0] if components else None
		if row.get("operation"):
			target = next((c for c in components if c["operation"] == row.get("operation")), target)
		if target is None:
			continue
		target["operation_product_in_components"].append(
			{
				"product": row.item_code,
				"quantity": row.qty,
				"unit": row.uom,
				"convertible": _uom_convertible(row.item_code, row.uom),
			}
		)

	# The anchor keeps materials on the BOM, not per routing operation: every operation after
	# the first consumes its predecessor's output (the semi-finished product), exactly as the
	# Qcadoo tree models the handover between technology operation components.
	for component in components[1:]:
		if component["operation_product_in_components"]:
			continue
		component["operation_product_in_components"].append(
			{
				"product": bom_doc.item,
				"quantity": bom_doc.get("quantity"),
				"unit": bom_doc.get("uom"),
				"convertible": True,
				"predecessor_output": True,
			}
		)

	active_orders = active_orders_for_recipe(bom)
	return {
		"number": bom_doc.name,
		"final_product": bom_doc.item,
		"routing": routing_name,
		"used_in_active_order": bool(active_orders),
		"active_orders": active_orders,
		"operation_components": components,
	}


def evaluate_recipe(bom: str, routing: str | None = None) -> validators.ValidationReport:
	"""Run the structural battery against the live anchor documents."""
	return validators.evaluate_recipe(recipe_snapshot(bom, routing))


# ------------------------------------------------------------------------- transition API


def transition(record: str | Any, target_state: str, reason: str | None = None) -> Any:
	"""Move a `Recipe Governance` record to `target_state`.

	All enforcement (legality, role gate, validators, in-use lock, predecessor outdating,
	audit row) lives in the DocType controller, so a Desk workflow action and this API
	behave identically.
	"""
	doc = record if hasattr(record, "doctype") else frappe.get_doc(GOVERNANCE_DOCTYPE, record)
	doc.gov_state = target_state
	if reason:
		doc.transition_reason = reason
	doc.save()
	return doc


# --------------------------------------------------------------------------- anchor hooks


def enforce_recipe_change_control(doc: Any, method: str | None = None) -> None:
	"""Change control on the anchor `BOM` (URS-W1-016 AC-1, URS-W1-017).

	Registered as a `doc_event` on `BOM` — the anchor DocType itself is never forked. Two
	refusals, both governance-driven:

	* a recipe referenced by an active order may not be touched at all (in-use lock);
	* an Accepted recipe is immutable, including the cancel-and-rewrite route: changes go
	  into a new BOM version whose governance record starts in Draft, and accepting that
	  successor outdates the predecessor.

	The anchor's own submit lock already refuses most field edits on a submitted BOM; this
	hook adds the governance-aware refusal (and covers cancelling, which the anchor allows).
	"""
	if doc.is_new():
		return
	state = gov_state(doc.name)
	if not state:
		return
	if method != "before_cancel" and not _material_change(doc):
		return

	orders = active_orders_for_recipe(doc.name)
	if orders:
		frappe.throw(
			_(
				"Rezept {0} kann nicht geändert werden: es wird von aktiven Fertigungsaufträgen "
				"verwendet ({1})."
			).format(doc.name, ", ".join(orders)),
			title=_("Verwendungssperre"),
		)
	if state != ACCEPTED:
		return
	frappe.throw(
		_(
			"Rezept {0} ist freigegeben (Freigabestatus: {1}) und damit unveränderlich. "
			"Änderungen erfordern eine neue Stücklistenversion; die Vorgängerversion wird bei "
			"deren Freigabe automatisch auf {2} gesetzt."
		).format(doc.name, _(state), _(OUTDATED)),
		title=_("Rezeptänderung gesperrt"),
	)


def _material_change(doc: Any) -> bool:
	"""True when the saved BOM differs from the stored one in a governed aspect."""
	before = doc.get_doc_before_save()
	if before is None:
		return True
	if (doc.get("routing") or "") != (before.get("routing") or ""):
		return True
	if (doc.get("quantity") or 0) != (before.get("quantity") or 0) or (doc.get("uom") or "") != (
		before.get("uom") or ""
	):
		return True
	return _lines(doc) != _lines(before)


def _lines(doc: Any) -> list[tuple[Any, ...]]:
	return [
		(row.get("item_code"), row.get("qty"), row.get("uom"), row.get("operation"))
		for row in doc.get("items") or []
	]


# --------------------------------------------------------------------------- descriptions


def describe_findings(findings: Sequence[validators.Finding]) -> str:
	"""Human-readable, German-first validator failure list for a refusal message."""
	lines = []
	for finding in findings:
		label = _(VALIDATOR_LABELS.get(finding.validator, finding.validator))
		lines.append(f"- {label}: {finding.subject}".rstrip(": "))
	return "\n".join(lines)


#: German labels for the validator ids; the pill and refusal messages never concatenate
#: translated fragments (design skill § i18n).
VALIDATOR_LABELS: Mapping[str, str] = {
	"technology_tree_set": "Arbeitsplan vorhanden",
	"in_component_quantities": "Mengen aller Einsatzstoffe gefüllt",
	"operation_input_components": "Einsatzstoffe je Arbeitsgang vorhanden",
	"final_product_declared": "Erzeugnis im Rezept deklariert",
	"operation_tree_units": "Einheiten im Rezeptbaum stimmig",
	"component_unit_convertible": "Einheit der Stücklistenposition umrechenbar",
	"not_used_in_active_order": "Rezept nicht in aktiven Aufträgen verwendet",
}
