"""Legacy Qcadoo rules, re-expressed in Python (never ported) — URS-W0-012.

Each function is a reading of the cited Java source in `SachetCognition/Chem_mes`
(branch `master`, commit 81d6bb5939). Semantics only: the Java is read, the rule is
re-expressed here, and the fixtures in `fixtures/` pin the resulting behaviour. Message
keys are kept identical to the legacy keys so refusal reasons stay comparable across the
migration.

Source paths below are relative to the `Chem_mes` repository root:

* `mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/OrderStateValidationService.java`
* `mes-plugins/mes-plugins-material-flow-resources/src/main/java/com/qcadoo/mes/materialFlowResources/service/ResourceManagementServiceImpl.java`
* `mes-plugins/mes-plugins-material-flow-resources/src/main/java/com/qcadoo/mes/materialFlowResources/constants/WarehouseAlgorithm.java`
* `mes-plugins/mes-plugins-technologies/src/main/java/com/qcadoo/mes/technologies/states/listener/TechnologyValidationService.java`
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .api import Verdict
from .loader import parse_de_date

FIELD_REQUIRED = "orders.order.orderStates.fieldRequired"
DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO = "orders.order.orderStates.doneQuantityMustBeGreaterThanZero"

EMPTY_TECHNOLOGY_TREE = "technologies.technology.validate.global.error.emptyTechnologyTree"
IN_COMPONENTS_QUANTITIES_NOT_FILLED = (
	"technologies.technology.validate.global.error.inComponentsQuantitiesNotFilled"
)
OPERATION_TREE_NOT_VALID = "technologies.technology.validate.error.OperationTreeNotValid"
UNITS_NOT_MATCH = "technologies.operationDetails.validate.error.UnitsNotMatch"
OUTPUT_UNITS_NOT_MATCH = "technologies.operationDetails.validate.error.OutputUnitsNotMatch"
ORDER_IN_PROGRESS = "technologies.technology.state.error.orderInProgress"

#: Required-field lists, verbatim from the legacy `Arrays.asList(...)` declarations.
ACCEPTANCE_REQUIRED_FIELDS = ("date_to", "date_from", "production_line", "technology")
COMPLETION_REQUIRED_FIELDS = ("date_to", "date_from", "done_quantity")

#: Qcadoo `WarehouseAlgorithm` enum values (WarehouseAlgorithm.java:26-27).
WAREHOUSE_ALGORITHMS = {
	"FIFO": "01fifo",
	"LIFO": "02lifo",
	"FEFO": "03fefo",
	"LEFO": "04lefo",
}


def _missing_fields(order: Mapping[str, Any], required: Sequence[str]) -> list[str]:
	"""Legacy `checkRequired`: a field is missing when its value is null.

	Baseline: `OrderStateValidationService.java:64-72` (`checkRequired`) — a null field
	yields one `fieldRequired` error per field, in declaration order.
	"""
	return [name for name in required if order.get(name) is None]


def evaluate_order_acceptance(order: Mapping[str, Any]) -> Verdict:
	"""Order acceptance gate: dateTo, dateFrom, productionLine and technology are required.

	Baseline: `OrderStateValidationService.java:44-47` (`validationOnAccepted`) — the
	transition to *accepted* is refused with `orders.order.orderStates.fieldRequired` for
	every null field among dateTo, dateFrom, productionLine, technology.
	"""
	errors = [FIELD_REQUIRED for _ in _missing_fields(order, ACCEPTANCE_REQUIRED_FIELDS)]
	return Verdict(allowed=not errors, errors=tuple(errors))


def evaluate_order_completion(order: Mapping[str, Any]) -> Verdict:
	"""Order completion gate: dates required and doneQuantity must be greater than zero.

	Baseline: `OrderStateValidationService.java:54-63` (`validationOnCompleted`) —
	dateTo/dateFrom/doneQuantity are required, and a doneQuantity that compares equal to
	zero adds `orders.order.orderStates.doneQuantityMustBeGreaterThanZero`. The legacy
	code suppresses that second error when the `ziepiwowarski` plugin is enabled; the
	Rheinwerk estate never ships that plugin, so the fixture models the plugin-disabled
	branch (`plugin_ziepiwowarski_enabled` defaults to false).
	"""
	errors = [FIELD_REQUIRED for _ in _missing_fields(order, COMPLETION_REQUIRED_FIELDS)]
	done_quantity = order.get("done_quantity")
	plugin_enabled = bool(order.get("plugin_ziepiwowarski_enabled", False))
	if done_quantity is not None and float(done_quantity) == 0 and not plugin_enabled:
		errors.append(DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO)
	return Verdict(allowed=not errors, errors=tuple(errors))


def _sort_key(resource: Mapping[str, Any], keys: Sequence[tuple[str, bool]]) -> tuple[Any, ...]:
	parts: list[Any] = []
	for field_name, ascending in keys:
		value = resource[field_name]
		if field_name == "expiration_date":
			value = parse_de_date(value).toordinal()
		elif field_name == "time":
			value = parse_de_date(value).toordinal() if "." in str(value) else float(value)
		else:
			value = float(value)
		parts.append(value if ascending else -value)
	return tuple(parts)


def picking_order(resources: Sequence[Mapping[str, Any]], algorithm: str) -> tuple[str, ...]:
	"""Disposal (picking) order of warehouse resources for a warehouse algorithm.

	Baseline: `ResourceManagementServiceImpl.java:1015-1027`
	(`getResourcesForWarehouseProductAndAlgorithm`) with the enum from
	`WarehouseAlgorithm.java:26-27`:

	* FIFO — `SearchOrders.asc(TIME)`
	* LIFO — `SearchOrders.desc(TIME)`
	* FEFO — `SearchOrders.asc(EXPIRATION_DATE)`, then `asc(AVAILABLE_QUANTITY)`
	* LEFO — `SearchOrders.desc(EXPIRATION_DATE)`, then `asc(AVAILABLE_QUANTITY)`

	`WarehouseAlgorithm.parseString` (`WarehouseAlgorithm.java:38-48`) falls back to FIFO
	for any unknown value, which is reproduced here.
	"""
	orders: dict[str, tuple[tuple[str, bool], ...]] = {
		"FIFO": (("time", True),),
		"LIFO": (("time", False),),
		"FEFO": (("expiration_date", True), ("available_quantity", True)),
		"LEFO": (("expiration_date", False), ("available_quantity", True)),
	}
	name = str(algorithm).upper()
	if name not in orders:
		name = "FIFO"
	ordered = sorted(resources, key=lambda resource: _sort_key(resource, orders[name]))
	return tuple(str(resource["batch"]) for resource in ordered)


def _check_in_component_quantities(technology: Mapping[str, Any]) -> str | None:
	"""Baseline: `TechnologyValidationService.java:91-144` (`checkIfEveryInComponentsHasQuantities`).

	The first input component that has no quantity — while it is not a
	`differentProductsInDifferentSizes` component — refuses the transition and the
	validator returns immediately.
	"""
	for component in technology.get("operation_components", []):
		for in_component in component.get("operation_product_in_components", []):
			different_sizes = bool(in_component.get("different_products_in_different_sizes", False))
			if not different_sizes and in_component.get("quantity") is None:
				return IN_COMPONENTS_QUANTITIES_NOT_FILLED
	return None


def _check_unit_match(component: Mapping[str, Any]) -> str | None:
	"""Baseline: `TechnologyValidationService.java:618-639` (`checkIfUnitMatch`).

	When `nextOperationAfterProducedType` is `02specified`, the operation's
	productionInOneCycle unit must equal the nextOperationAfterProducedQuantity unit.
	A null productionInOneCycle unit passes this validator (checked by the next one).
	"""
	production_unit = component.get("production_in_one_cycle_unit")
	if production_unit is None:
		return None
	if component.get(
		"next_operation_after_produced_type"
	) == "02specified" and production_unit != component.get("next_operation_after_produced_quantity_unit"):
		return UNITS_NOT_MATCH
	return None


def _check_units_in_technology_match(component: Mapping[str, Any]) -> str | None:
	"""Baseline: `TechnologyValidationService.java:641-676` (`checkIfUnitsInTechnologyMatch`).

	The operation's productionInOneCycle unit must be set and must equal the unit of the
	operation's main output product.
	"""
	production_unit = component.get("production_in_one_cycle_unit")
	if production_unit is None:
		return OUTPUT_UNITS_NOT_MATCH
	output_unit = component.get("main_output_product_unit")
	if output_unit is not None and production_unit != output_unit:
		return OUTPUT_UNITS_NOT_MATCH
	return None


def evaluate_technology(technology: Mapping[str, Any]) -> Verdict:
	"""Technology structural validators (tree / units / in-use).

	Baseline: `TechnologyValidationService.java:91-707`, in the order the legacy state
	listener applies them:

	1. `checkIfTechnologyTreeIsSet` (:678-705) — an empty operation tree is refused.
	2. `checkIfEveryInComponentsHasQuantities` (:91-144) — input components need quantities.
	3. `checkIfTreeOperationIsValid` (:546-580) — per operation component, `checkIfUnitMatch`
	   (:618-639) then `checkIfUnitsInTechnologyMatch` (:641-676); any failure adds the
	   aggregate `OperationTreeNotValid` error.
	4. `checkIfTechnologyIsNotUsedInActiveOrder` (:232-238) — a technology used by an
	   active order cannot change state.

	Returned `errors` are the legacy message keys in that order; W1 consumes these
	fixtures when it implements the real validators.
	"""
	errors: list[str] = []

	components = technology.get("operation_components", [])
	if not components:
		errors.append(EMPTY_TECHNOLOGY_TREE)
	else:
		quantities_error = _check_in_component_quantities(technology)
		if quantities_error:
			errors.append(quantities_error)

		tree_errors: list[str] = []
		for component in components:
			component_error = _check_unit_match(component) or _check_units_in_technology_match(component)
			if component_error:
				tree_errors.append(component_error)
		if tree_errors:
			errors.extend(tree_errors)
			errors.append(OPERATION_TREE_NOT_VALID)

	if bool(technology.get("used_in_active_order", False)):
		errors.append(ORDER_IN_PROGRESS)

	return Verdict(allowed=not errors, errors=tuple(errors))
