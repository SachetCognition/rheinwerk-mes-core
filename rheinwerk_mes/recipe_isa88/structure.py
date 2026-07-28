"""ISA-88 structure integrity (W2-6, URS-W2-020 AC-3).

White space in all three legacy systems (dossier §6.3) — designed from the URS. The
procedural view (`ISA88 Recipe` → unit procedures → phases) layers over the governed
anchor BOM/Routing pair without forking either; these checks keep it consistent with the
material master:

* every phase that charges a `material` must reference a component line of the linked BOM
  (the material master cannot be bypassed by the procedural view);
* every phase's `unit_procedure` grouping key must name a declared unit procedure.

Kept as a pure helper over the document so the controller and the acceptance tests call
the same code. Messages are German-first and name the phase and the material (URS-W2-020
AC-3), never concatenated fragments.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def bom_component_items(bom: str) -> set[str]:
	"""Item codes that are component lines of `bom` (the recipe's material master)."""
	return {
		row.item_code
		for row in frappe.get_all(
			"BOM Item", filters={"parent": bom}, fields=["item_code"], ignore_permissions=True
		)
	}


def validate_structure(recipe: Any) -> None:
	"""Refuse to save an `ISA88 Recipe` whose procedural view is inconsistent (URS-W2-020 AC-3)."""
	unit_procedure_ids = {(up.unit_procedure_id or "").strip() for up in recipe.get("unit_procedures") or []}
	components = bom_component_items(recipe.bom) if recipe.bom else set()

	for phase in recipe.get("phases") or []:
		grouping = (phase.unit_procedure or "").strip()
		if grouping and grouping not in unit_procedure_ids:
			frappe.throw(
				_("Phase {0} verweist auf die unbekannte Teilanlage {1}.").format(phase.phase_name, grouping),
				title=_("Unbekannte Teilanlage"),
			)
		if phase.material and phase.material not in components:
			frappe.throw(
				_(
					"Phase {0} verweist auf das Material {1}, das nicht in der Stückliste {2} enthalten ist."
				).format(phase.phase_name, phase.material, recipe.bom),
				title=_("Material nicht in Stückliste"),
			)
