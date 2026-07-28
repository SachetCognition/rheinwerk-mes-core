"""ISA-88 recipe scaling (W2-6, URS-W2-021).

Scale an `ISA88 Recipe` to a target batch size and materialise the result as a **new
governed recipe version**: a new anchor BOM version (never a fork), its `Recipe Governance`
record starting in Draft (W1-4), and a new `ISA88 Recipe` recording the source and the
scale factor. White space in all three legacy systems (dossier §6.3) — designed from the
URS. Design and decisions: `docs/design/W2-isa88.md`.

All arithmetic runs in `Decimal`, exactly like the W0 UoM code
(`rheinwerk_mes.manufacturing_core.uom`), so pack/charge quantities never pick up binary
float drift and mass balance is preserved: every phase quantity and the declared output are
scaled by the *same* factor, so ``Σ(scaled inputs) = f · Σ(inputs) = f · output``.

Three guard rails (URS-W2-021):

* **equipment limit (AC-2)** — a work centre's declared working-volume ceiling
  (`Workstation.rw_max_working_qty`) refuses a scale whose charge would exceed it;
* **rounding guard (AC-3)** — a scaled quantity that would quantise to zero is never
  silently zeroed; it is flagged for technologist confirmation and, once confirmed, kept
  at full precision;
* **governance (AC-1 / URS-W2-022)** — the scaled recipe is a new BOM version whose
  governance state starts in Draft.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.recipe_isa88 import governance

#: kg carrying precision (10 g) — the rounding guard fires when a scaled quantity would
#: quantise to zero at this precision (URS-W2-021 AC-3). Decision D3, `docs/design/W2-isa88.md`.
QUANTITY_PRECISION = 2

#: Precision at which a sub-precision quantity is preserved once the technologist confirms
#: the rounding, so it is never silently zeroed.
CONFIRMED_PRECISION = 6

WORKSTATION_LIMIT_FIELD = "rw_max_working_qty"


def _dec(value: Any) -> Decimal:
	"""Parse any numeric-ish value into `Decimal` via its string form (no float drift)."""
	return Decimal(str(value or 0))


def scale_factor(source_batch_size: Any, target_batch_size: Any) -> Decimal:
	"""Exact `Decimal` scale factor ``target / source`` (URS-W2-021 AC-1)."""
	source = _dec(source_batch_size)
	if source <= 0:
		frappe.throw(
			_("Die Nennchargengröße des Ausgangsrezepts muss größer als 0 sein."),
			title=_("Ungültige Chargengröße"),
		)
	target = _dec(target_batch_size)
	if target <= 0:
		frappe.throw(_("Die Zielchargengröße muss größer als 0 sein."), title=_("Ungültige Chargengröße"))
	return target / source


def _quantize(value: Decimal, precision: int) -> Decimal:
	return value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)


def _kg(value: Decimal | Any) -> str:
	"""German-first mass rendering (decimal comma, trailing zeros trimmed, unit kg)."""
	text = f"{_dec(value):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


def _workstation_limit(workstation: str | None) -> Decimal:
	"""Declared working-volume ceiling of a work centre; 0 means no declared limit."""
	if not workstation:
		return Decimal(0)
	if not frappe.get_meta("Workstation").get_field(WORKSTATION_LIMIT_FIELD):
		return Decimal(0)
	return _dec(frappe.db.get_value("Workstation", workstation, WORKSTATION_LIMIT_FIELD))


def _phases_for(recipe: Any, unit_procedure_id: str) -> list[Any]:
	return [p for p in recipe.get("phases") or [] if (p.unit_procedure or "").strip() == unit_procedure_id]


def equipment_violations(recipe: Any, factor: Decimal) -> list[dict[str, Any]]:
	"""Unit procedures whose scaled charge would exceed the work centre limit (AC-2).

	The scaled charge of a unit procedure is the sum of its phases' scaled material
	quantities — the mass charged into that work centre for one batch.
	"""
	violations: list[dict[str, Any]] = []
	for up in recipe.get("unit_procedures") or []:
		limit = _workstation_limit(up.workstation)
		if limit <= 0:
			continue
		phases = _phases_for(recipe, (up.unit_procedure_id or "").strip())
		charge = sum((_dec(p.quantity) * factor for p in phases if p.material), Decimal(0))
		if charge > limit:
			material_phases = [p.phase_name for p in phases if p.material]
			violations.append(
				{
					"unit_procedure": up.unit_procedure_name or up.unit_procedure_id,
					"workstation": up.workstation,
					"limit": limit,
					"charge": charge,
					"phases": material_phases,
				}
			)
	return violations


def _refuse_equipment(violations: list[dict[str, Any]], target_batch_size: Any) -> None:
	lines = [
		_("- Teilanlage {0} (Arbeitsplatz {1}, Phasen {2}): Charge {3} überschreitet Grenze {4}").format(
			v["unit_procedure"],
			v["workstation"],
			", ".join(v["phases"]) or "—",
			_kg(v["charge"]),
			_kg(v["limit"]),
		)
		for v in violations
	]
	frappe.throw(
		_("Skalierung auf {0} abgelehnt — Arbeitsvolumen überschritten:").format(_kg(target_batch_size))
		+ "\n"
		+ "\n".join(lines),
		title=_("Arbeitsvolumen überschritten"),
	)


def _scaled_quantity(exact: Decimal, confirm_rounding: bool) -> tuple[Decimal, bool]:
	"""Return (stored quantity, below_precision). A sub-precision value is never zeroed:
	once confirmed it is kept at `CONFIRMED_PRECISION` (URS-W2-021 AC-3)."""
	quantized = _quantize(exact, QUANTITY_PRECISION)
	below = exact != 0 and quantized == 0
	if not below:
		return quantized, False
	if confirm_rounding:
		return _quantize(exact, CONFIRMED_PRECISION), True
	return quantized, True


def _refuse_rounding(flagged: list[dict[str, Any]], target_batch_size: Any) -> None:
	lines = [
		_("- Phase {0} ({1}): skalierte Menge {2}").format(f["phase"], f["material"], _kg(f["exact"]))
		for f in flagged
	]
	frappe.throw(
		_(
			"Skalierung auf {0} ergibt Mengen unterhalb der Mengengenauigkeit. Diese müssen vom "
			"Technologen bestätigt werden, statt still auf 0 gerundet zu werden:"
		).format(_kg(target_batch_size))
		+ "\n"
		+ "\n".join(lines),
		title=_("Rundung bestätigen"),
	)


def scale_recipe(source: str | Any, target_batch_size: Any, confirm_rounding: bool = False) -> Any:
	"""Scale `source` (an `ISA88 Recipe`) to `target_batch_size` (URS-W2-021, URS-W2-022).

	Creates and returns a new `ISA88 Recipe` referencing a new, submitted anchor BOM version
	whose `Recipe Governance` record starts in Draft. Refuses (before creating anything) when
	an equipment ceiling is exceeded, or — unless `confirm_rounding` — when a scaled quantity
	would round to zero.
	"""
	recipe = source if hasattr(source, "doctype") else frappe.get_doc("ISA88 Recipe", source)
	factor = scale_factor(recipe.batch_size, target_batch_size)
	target = _dec(target_batch_size)

	violations = equipment_violations(recipe, factor)
	if violations:
		_refuse_equipment(violations, target)

	scaled_phases, flagged, rounding_flag = _scale_phases(recipe, factor, confirm_rounding)
	if flagged and not confirm_rounding:
		_refuse_rounding(flagged, target)

	new_bom = _build_scaled_bom(recipe, scaled_phases, target)
	_ensure_governance(new_bom, recipe.routing)
	return _build_scaled_recipe(recipe, new_bom, factor, target, scaled_phases, rounding_flag)


def _scale_phases(
	recipe: Any, factor: Decimal, confirm_rounding: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
	"""Scale every phase's material quantity; collect sub-precision flags (AC-3)."""
	scaled: list[dict[str, Any]] = []
	flagged: list[dict[str, Any]] = []
	for phase in recipe.get("phases") or []:
		row: dict[str, Any] = {
			"unit_procedure": phase.unit_procedure,
			"phase_name": phase.phase_name,
			"phase_type": phase.phase_type,
			"sequence": phase.sequence,
			"material": phase.material,
			"uom": phase.uom,
			"duration_min": phase.duration_min,
			"quantity": None,
		}
		if phase.material:
			exact = _dec(phase.quantity) * factor
			stored, below = _scaled_quantity(exact, confirm_rounding)
			row["quantity"] = stored
			if below:
				flagged.append({"phase": phase.phase_name, "material": phase.material, "exact": exact})
		scaled.append(row)
	return scaled, flagged, bool(flagged)


def _build_scaled_bom(recipe: Any, scaled_phases: list[dict[str, Any]], target: Decimal) -> str:
	"""Create a submitted new anchor BOM version from the scaled phase materials.

	Materials are aggregated by item so the BOM stays the material master; `quantity` is the
	target batch size. The anchor's own versioned naming yields the next `-NNN` version — a
	real BOM version, never a fork.
	"""
	source_bom = frappe.get_doc("BOM", recipe.bom)
	totals: dict[str, Decimal] = {}
	for phase in scaled_phases:
		if not phase["material"]:
			continue
		totals[phase["material"]] = totals.get(phase["material"], Decimal(0)) + _dec(phase["quantity"])

	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": source_bom.item,
			"company": source_bom.company,
			"quantity": float(target),
			"currency": source_bom.get("currency") or "EUR",
			"is_active": 1,
			"is_default": 0,
			"with_operations": source_bom.get("with_operations") or 0,
			"routing": recipe.routing or source_bom.get("routing"),
			"rm_cost_as_per": source_bom.get("rm_cost_as_per") or "Valuation Rate",
		}
	)
	for item_code, qty in totals.items():
		bom.append("items", {"item_code": item_code, "qty": float(qty)})
	bom.insert()
	bom.submit()
	return bom.name


def _ensure_governance(bom: str, routing: str | None) -> str:
	"""Create the scaled recipe's `Recipe Governance` record — it starts in Draft (AC-1)."""
	existing = governance.governance_name(bom)
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": governance.GOVERNANCE_DOCTYPE, "bom": bom, "routing": routing}).insert()
	return doc.name


def _build_scaled_recipe(
	recipe: Any,
	new_bom: str,
	factor: Decimal,
	target: Decimal,
	scaled_phases: list[dict[str, Any]],
	rounding_flag: bool,
) -> Any:
	scaled = frappe.get_doc(
		{
			"doctype": "ISA88 Recipe",
			"recipe_name": _("{0} – Charge {1}").format(recipe.recipe_name, _kg(target)),
			"bom": new_bom,
			"routing": recipe.routing,
			"batch_size": float(target),
			"source_recipe": recipe.name,
			"scale_factor": float(factor),
			"rounding_confirmation_required": 1 if rounding_flag else 0,
		}
	)
	for up in recipe.get("unit_procedures") or []:
		scaled.append(
			"unit_procedures",
			{
				"unit_procedure_id": up.unit_procedure_id,
				"unit_procedure_name": up.unit_procedure_name,
				"sequence": up.sequence,
				"operation": up.operation,
				"workstation": up.workstation,
			},
		)
	for phase in scaled_phases:
		scaled.append(
			"phases",
			{
				"unit_procedure": phase["unit_procedure"],
				"phase_name": phase["phase_name"],
				"phase_type": phase["phase_type"],
				"sequence": phase["sequence"],
				"material": phase["material"],
				"quantity": float(phase["quantity"]) if phase["quantity"] is not None else None,
				"uom": phase["uom"],
				"duration_min": phase["duration_min"],
			},
		)
	scaled.insert()
	return scaled
