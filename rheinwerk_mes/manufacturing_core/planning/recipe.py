"""Recipe governance for planning — only Accepted recipes are plannable (URS-W3-002).

Qcadoo lets a master plan reference only *accepted* technologies (CDM-04, the same reading
the W1 `recipe_accepted_gate` applies to order acceptance). The master-scheduling side of
that rule lives here: before any BOM is exploded into requirements it is judged through
`recipe_isa88.governance.gov_state` (W1-4), and a Draft (or otherwise non-Accepted) recipe
reference is refused as a **hard gate** — a modal naming rule, record and resolution
(design skill § "Hard gates look hard") — and written to the immutable `Execution Gate Log`
(URS-W1-033) through the shared `execution_gating.audit` API. Neither the governance API
nor the audit log is re-implemented here.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import strip_html

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.execution_gating.gates import hard_gate_message
from rheinwerk_mes.recipe_isa88 import governance

#: Gate identifier recorded on every planning refusal row.
PLANNING_RECIPE_GATE = "planning_recipe_accepted"


def plannable_bom(item_code: str, bom_no: str | None = None) -> str:
	"""Resolve the recipe to plan `item_code` against and assert it is Accepted.

	An explicit `bom_no` wins (the planner chose a version); otherwise the item's active
	default BOM is used. The resolved recipe is gated through `assert_plannable`, so callers
	never receive a Draft recipe reference.
	"""
	recipe = bom_no or _default_bom(item_code)
	if not recipe or not frappe.db.exists("BOM", recipe):
		frappe.throw(
			_("Für Artikel {0} ist kein aktives Rezept (Stückliste) hinterlegt.").format(item_code),
			title=_("Kein Rezept"),
		)
	assert_plannable(recipe)
	return recipe


def assert_plannable(bom_no: str) -> None:
	"""Refuse planning a recipe whose `gov_state` is not Accepted (hard gate + audit).

	The refusal names the **rule** (only Accepted recipes are plannable), the **record**
	(the offending recipe and its governance state) and the **resolution** (release it or
	pick an Accepted version), then raises it as one modal. It is the master-scheduling
	twin of `execution_gating.gates.recipe_accepted_gate`.
	"""
	state = governance.gov_state(bom_no)
	if state == governance.ACCEPTED:
		return

	rule = _(
		"In die Produktionsplanung dürfen nur freigegebene Rezepte einfließen (Freigabestatus Accepted)."
	)
	record = _("Rezept {0} — Freigabestatus {1}").format(bom_no, _(state) if state else _("nicht geführt"))
	resolution = _("Rezept über die Rezeptlenkung freigeben oder eine freigegebene Rezeptversion auswählen.")

	if frappe.db.exists("BOM", bom_no):
		audit.log_refusal(
			gate=PLANNING_RECIPE_GATE,
			rule=rule,
			document=frappe.get_doc("BOM", bom_no),
			detail=strip_html(f"{record} — {resolution}"),
		)
	frappe.throw(
		hard_gate_message(rule, record, resolution),
		title=_("Planung abgelehnt"),
	)


def _default_bom(item_code: str) -> str | None:
	return frappe.db.get_value("BOM", {"item": item_code, "is_active": 1, "is_default": 1}, "name")
