"""Structural recipe validators (URS-W1-015, W1-4).

Re-implementation — never a port — of the Qcadoo technology validation battery
(`SachetCognition/Chem_mes@master`,
`mes-plugins/mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/states/
listener/TechnologyValidationService.java:91-707`), scoped to the anchor BOM/Routing
split (CDM-04) and ordered exactly as the legacy state-change aspect applies it
(`states/aop/listener/TechnologyValidationAspect.java:72-141`).

The battery is a **pure function over a plain mapping** ("recipe snapshot"), so it runs
offline, is directly comparable with the W0 characterisation fixtures
(`tests/characterisation/fixtures/technology_validation.json`) and is reused unchanged by
the DocType-facing governance hooks, which build the snapshot from the anchor documents
(`governance.recipe_snapshot`).

Snapshot shape (keys mirror the legacy field names so parity stays machine-checkable)::

    {
      "number": "BOM-RW-CHM-0003-001",        # recipe identifier
      "final_product": "RW-CHM-0003",         # optional: BOM output item (extension check)
      "used_in_active_order": False,
      "active_orders": ["PO-2026-0001"],      # optional: names for the refusal message
      "operation_components": [
        {
          "node_number": "1",
          "operation": "MIX",
          "production_in_one_cycle_unit": "kg",
          "main_output_product_unit": "kg",
          "main_output_product": "RW-CHM-0003",          # optional (extension check)
          "next_operation_after_produced_type": "01all",
          "next_operation_after_produced_quantity_unit": None,
          "operation_product_in_components": [
            {"product": "RW-CHM-0001", "quantity": 400, "unit": "kg", "convertible": True},
          ],
        }
      ],
    }
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: Legacy Qcadoo message keys, verbatim, so the parity contract compares like with like.
EMPTY_TECHNOLOGY_TREE = "technologies.technology.validate.global.error.emptyTechnologyTree"
IN_COMPONENTS_QUANTITIES_NOT_FILLED = (
	"technologies.technology.validate.global.error.inComponentsQuantitiesNotFilled"
)
NO_INPUT_COMPONENTS = "technologies.technology.validate.global.error.noInputComponents"
NO_FINAL_PRODUCT_IN_TECHNOLOGY_TREE = (
	"technologies.technology.validate.global.error.noFinalProductInTechnologyTree"
)
OPERATION_TREE_NOT_VALID = "technologies.technology.validate.error.OperationTreeNotValid"
UNITS_NOT_MATCH = "technologies.operationDetails.validate.error.UnitsNotMatch"
OUTPUT_UNITS_NOT_MATCH = "technologies.operationDetails.validate.error.OutputUnitsNotMatch"
ORDER_IN_PROGRESS = "technologies.technology.state.error.orderInProgress"

#: Target-only key: the anchor keeps UoM conversions on the Item, so a BOM line may carry a
#: unit that has no conversion for its item — a failure mode Qcadoo cannot express
#: (its products own a single unit). Deliberate extension, recorded in
#: `docs/design/W1-recipe-governance.md`.
COMPONENT_UNIT_NOT_CONVERTIBLE = "rheinwerk.recipe.validate.error.componentUnitNotConvertible"

#: Validator ids stored on the governance record, in execution order.
VALIDATORS: tuple[str, ...] = (
	"technology_tree_set",
	"in_component_quantities",
	"operation_input_components",
	"final_product_declared",
	"operation_tree_units",
	"component_unit_convertible",
	"not_used_in_active_order",
)


@dataclass(frozen=True)
class Verdict:
	"""Outcome of the validator battery.

	Mirrors `tests/characterisation/api.Verdict`: `allowed` is False when the recipe may
	not be accepted, `errors` holds the message keys in the order the validators raise
	them, so `CHAR-TECH-VALIDATE-01` compares target and legacy behaviour key by key.
	"""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Finding:
	"""One validator failure, with the record it names (URS-W1-015 AC-1)."""

	validator: str
	message_key: str
	subject: str = ""


@dataclass(frozen=True)
class ValidationReport:
	"""Everything the governance record stores about one validation run."""

	validators_run: tuple[str, ...]
	findings: tuple[Finding, ...]

	@property
	def verdict(self) -> Verdict:
		errors = tuple(finding.message_key for finding in self.findings)
		return Verdict(allowed=not errors, errors=errors)

	def failed_validators(self) -> tuple[str, ...]:
		seen: list[str] = []
		for finding in self.findings:
			if finding.validator not in seen:
				seen.append(finding.validator)
		return tuple(seen)


def _components(technology: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
	return technology.get("operation_components") or []


def _node(component: Mapping[str, Any]) -> str:
	"""`OPERATION/NODE` reference used in refusal messages (legacy vars of the same name)."""
	operation = component.get("operation") or ""
	node_number = component.get("node_number") or ""
	return f"{operation}/{node_number}".strip("/")


def _check_in_component_quantities(technology: Mapping[str, Any]) -> Finding | None:
	"""`TechnologyValidationService.java:91-144` (`checkIfEveryInComponentsHasQuantities`).

	The first input component without a quantity — unless it is a
	`differentProductsInDifferentSizes` component — refuses the transition, and the legacy
	validator returns immediately (so no further validator contributes a message).
	"""
	for component in _components(technology):
		for in_component in component.get("operation_product_in_components") or []:
			if in_component.get("different_products_in_different_sizes"):
				continue
			if in_component.get("quantity") is None:
				return Finding(
					"in_component_quantities",
					IN_COMPONENTS_QUANTITIES_NOT_FILLED,
					f"{_node(component)}: {in_component.get('product') or ''}".strip(),
				)
	return None


def _check_operation_input_components(technology: Mapping[str, Any]) -> Finding | None:
	"""`TechnologyValidationService.java:186-228` (`checkIfEveryOperationHasInComponents`).

	Every operation must consume at least one input component, and every input component
	must name a product. On the anchor this is the BOM-completeness check: a BOM without
	component lines leaves its routing operations without inputs (URS-W1-015 AC-2).
	"""
	for component in _components(technology):
		in_components = component.get("operation_product_in_components") or []
		if not in_components or any(not row.get("product") for row in in_components):
			return Finding("operation_input_components", NO_INPUT_COMPONENTS, _node(component))
	return None


def _check_final_product_declared(technology: Mapping[str, Any]) -> Finding | None:
	"""`TechnologyValidationService.java:266-293`
	(`checkTopComponentsProducesProductForTechnology`).

	The recipe's output must be produced by the tree. On the anchor the BOM's `item` is the
	declared output and the routing's operations carry the produced product; the check is
	skipped when the snapshot declares no output product (the characterisation fixtures do
	not model outputs beyond their unit).
	"""
	final_product = technology.get("final_product")
	if not final_product:
		return None
	outputs = {component.get("main_output_product") for component in _components(technology)}
	if outputs == {None} or final_product in outputs:
		return None
	return Finding("final_product_declared", NO_FINAL_PRODUCT_IN_TECHNOLOGY_TREE, str(final_product))


def _check_unit_match(component: Mapping[str, Any]) -> Finding | None:
	"""`TechnologyValidationService.java:618-639` (`checkIfUnitMatch`).

	With `nextOperationAfterProducedType` = `02specified` the operation's
	productionInOneCycle unit must equal the passed-on quantity's unit; a null
	productionInOneCycle unit passes here and is caught by the next validator.
	"""
	production_unit = component.get("production_in_one_cycle_unit")
	if production_unit is None:
		return None
	if component.get(
		"next_operation_after_produced_type"
	) == "02specified" and production_unit != component.get("next_operation_after_produced_quantity_unit"):
		return Finding("operation_tree_units", UNITS_NOT_MATCH, _node(component))
	return None


def _check_units_in_technology_match(component: Mapping[str, Any]) -> Finding | None:
	"""`TechnologyValidationService.java:641-676` (`checkIfUnitsInTechnologyMatch`).

	The operation's productionInOneCycle unit must be set and must equal the unit of its
	main output product. On the anchor this is the BOM `uom` vs. output-item `stock_uom`
	comparison (mass in kg, URS-W1-015).
	"""
	production_unit = component.get("production_in_one_cycle_unit")
	if production_unit is None:
		return Finding("operation_tree_units", OUTPUT_UNITS_NOT_MATCH, _node(component))
	output_unit = component.get("main_output_product_unit")
	if output_unit is not None and production_unit != output_unit:
		return Finding("operation_tree_units", OUTPUT_UNITS_NOT_MATCH, _node(component))
	return None


def _check_operation_tree_units(technology: Mapping[str, Any]) -> list[Finding]:
	"""`TechnologyValidationService.java:546-580` (`checkIfTreeOperationIsValid`).

	Per operation component `checkIfUnitMatch` then `checkIfUnitsInTechnologyMatch`
	(short-circuiting per component); any failure adds the aggregate
	`OperationTreeNotValid` error after the individual ones.
	"""
	findings: list[Finding] = []
	for component in _components(technology):
		finding = _check_unit_match(component) or _check_units_in_technology_match(component)
		if finding:
			findings.append(finding)
	if findings:
		findings.append(
			Finding("operation_tree_units", OPERATION_TREE_NOT_VALID, technology.get("number") or "")
		)
	return findings


def _check_component_units_convertible(technology: Mapping[str, Any]) -> list[Finding]:
	"""Anchor-scoped UoM consistency (URS-W1-015 AC-1) — target-only extension.

	A BOM line may be measured in a unit other than its item's stock UoM; acceptance then
	requires an item-level UoM conversion for that unit (URS-W0-004). The check is inert
	when the snapshot carries no unit information, which keeps the legacy fixtures green.
	"""
	findings: list[Finding] = []
	for component in _components(technology):
		for in_component in component.get("operation_product_in_components") or []:
			unit = in_component.get("unit")
			if unit is None or in_component.get("convertible") is not False:
				continue
			findings.append(
				Finding(
					"component_unit_convertible",
					COMPONENT_UNIT_NOT_CONVERTIBLE,
					f"{_node(component)}: {in_component.get('product') or ''} ({unit})".strip(),
				)
			)
	return findings


def evaluate_recipe(technology: Mapping[str, Any]) -> ValidationReport:
	"""Run the W1-scoped validator battery over a recipe snapshot.

	Execution order follows `TechnologyValidationAspect.java:72-141`: tree set → input
	quantities → operation inputs → declared output → per-operation unit checks →
	(target extension) component-unit convertibility → in-use lock
	(`preValidationOnOutdatingOrDeclining`, :135-141).
	"""
	findings: list[Finding] = []
	components = _components(technology)

	if not components:
		findings.append(Finding("technology_tree_set", EMPTY_TECHNOLOGY_TREE, technology.get("number") or ""))
	else:
		quantities = _check_in_component_quantities(technology)
		if quantities:
			# Legacy returns from the aspect as soon as this validator fails (:81-83).
			return ValidationReport(VALIDATORS, (quantities,))

		inputs = _check_operation_input_components(technology)
		if inputs:
			return ValidationReport(VALIDATORS, (inputs,))

		final_product = _check_final_product_declared(technology)
		if final_product:
			findings.append(final_product)

		findings.extend(_check_operation_tree_units(technology))
		findings.extend(_check_component_units_convertible(technology))

	if technology.get("used_in_active_order"):
		orders = technology.get("active_orders") or []
		findings.append(
			Finding("not_used_in_active_order", ORDER_IN_PROGRESS, ", ".join(str(o) for o in orders))
		)

	return ValidationReport(VALIDATORS, tuple(findings))


def evaluate_technology(technology: Mapping[str, Any]) -> Verdict:
	"""Parity entrypoint: the battery's verdict for one recipe snapshot.

	This is the function the W0 characterisation harness resolves through
	`rheinwerk_mes.manufacturing_core.contracts.evaluate_technology`
	(`tests/characterisation/api.ENTRYPOINTS`), so `CHAR-TECH-VALIDATE-01` executes
	against production code.
	"""
	return evaluate_recipe(technology).verdict
