"""Recipe governance — the `gov_state` read API for the anchor BOM (W1-4).

Requirement scope for this slice: URS-W1-014 governs a recipe's approval lifecycle with a
five-state `gov_state` (Draft → Checked → Accepted, with Outdated/Declined terminal), and
sibling requirements read that state to gate the shop floor — notably URS-W1-006, where an
order may only be accepted against an *Accepted* recipe (CDM-04 / ADR-006).

Model: the anchor `BOM`/`Routing` split is kept and never forked. The recipe's governance
state lives on a `gov_state` Custom Field this app owns on the anchor `BOM`, so a caller
reads it without touching upstream ERPNext code::

    from rheinwerk_mes.recipe_isa88.governance import gov_state, is_accepted

    gov_state("BOM-RW-CHM-0003-001")     # -> "Accepted" | "Draft" | … | "" when ungoverned
    is_accepted("BOM-RW-CHM-0003-001")   # -> True/False

Legacy baseline (semantics only, re-implemented in Python):
`SachetCognition/Chem_mes@master` ·
`mes-plugins/mes-plugins-technologies/.../constants/TechnologyState.java:33-66`.
"""

from __future__ import annotations

import frappe

GOVERNANCE_FIELD = "gov_state"

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


def gov_state(recipe: str) -> str:
	"""Governance state of `recipe` (a BOM name), or `""` when it is not governed.

	The gate other children use (URS-W1-006: an order may only be accepted against an
	Accepted recipe). Ungoverned recipes deliberately return the empty string rather than
	Draft, so a caller can distinguish "not governed yet" from "still in draft".
	"""
	if not recipe:
		return ""
	return frappe.db.get_value("BOM", recipe, GOVERNANCE_FIELD) or ""


def is_accepted(recipe: str) -> bool:
	"""True when `recipe` carries an Accepted governance state."""
	return gov_state(recipe) == ACCEPTED


def can_change(current: str, target: str) -> bool:
	"""Legality of a `gov_state` transition (`TechnologyState.java:33-66`)."""
	return target in TRANSITIONS.get(current, ())
