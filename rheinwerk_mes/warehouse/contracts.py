"""Warehouse disposal-algorithm parity contract (URS-W1-020, CHAR-FEFO-PICK-01).

This module owns the W0 harness handover entrypoint
`rheinwerk_mes.warehouse.contracts.picking_order` (see `tests/characterisation/api.py`
`ENTRYPOINTS["picking_order"]`). As soon as this function exists, `CHAR-FEFO-PICK-01`
stops running against the fixture-encoded legacy rule and executes against production
code with the same fixtures and no test change — the parity guarantee ADR-001 asks for.

It is a **pure function over plain mappings** (no Frappe site required) so it stays
runnable inside the offline characterisation suite; the site-facing disposal logic in
`rheinwerk_mes.warehouse.disposal` builds those mappings from the anchor ledger and
delegates here.

Re-implements — never ports — the Qcadoo warehouse-algorithm ordering:
`mes-plugins/mes-plugins-material-flow-resources/src/main/java/com/qcadoo/mes/
materialFlowResources/service/ResourceManagementServiceImpl.java:1015-1027`
(`getResourcesForWarehouseProductAndAlgorithm`) with the enum and fallback in
`.../constants/WarehouseAlgorithm.java:26-27,38-48` (`SachetCognition/Chem_mes@master`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: Qcadoo `WarehouseAlgorithm` values (WarehouseAlgorithm.java:26-27).
WAREHOUSE_ALGORITHMS: dict[str, str] = {
	"FIFO": "01fifo",
	"LIFO": "02lifo",
	"FEFO": "03fefo",
	"LEFO": "04lefo",
}

#: SearchOrders per algorithm — (field, ascending) tuples applied in order.
#: FIFO asc(TIME); LIFO desc(TIME); FEFO asc(EXPIRATION_DATE), asc(AVAILABLE_QUANTITY);
#: LEFO desc(EXPIRATION_DATE), asc(AVAILABLE_QUANTITY).
_SEARCH_ORDERS: dict[str, tuple[tuple[str, bool], ...]] = {
	"FIFO": (("time", True),),
	"LIFO": (("time", False),),
	"FEFO": (("expiration_date", True), ("available_quantity", True)),
	"LEFO": (("expiration_date", False), ("available_quantity", True)),
}


def _parse_de_date_ordinal(value: str) -> int:
	"""German-first DD.MM.YYYY → proleptic-Gregorian ordinal (loader.parse_de_date parity)."""
	day, month, year = (int(part) for part in str(value).split("."))
	from datetime import date

	return date(year, month, day).toordinal()


def _sort_value(resource: Mapping[str, Any], field: str) -> float:
	if field == "expiration_date":
		return float(_parse_de_date_ordinal(resource[field]))
	if field == "time":
		raw = resource[field]
		return float(_parse_de_date_ordinal(raw)) if "." in str(raw) else float(raw)
	return float(resource[field])


def _sort_key(resource: Mapping[str, Any], keys: Sequence[tuple[str, bool]]) -> tuple[float, ...]:
	return tuple(
		_sort_value(resource, field) if ascending else -_sort_value(resource, field)
		for field, ascending in keys
	)


def normalise_algorithm(algorithm: str) -> str:
	"""`WarehouseAlgorithm.parseString`: unknown values fall back to FIFO."""
	name = str(algorithm).upper()
	return name if name in _SEARCH_ORDERS else "FIFO"


def picking_order(resources: Sequence[Mapping[str, Any]], algorithm: str) -> tuple[str, ...]:
	"""Disposal (picking) order of warehouse resources under `algorithm`.

	Each resource is a mapping with keys `batch`, `expiration_date` (DD.MM.YYYY),
	`available_quantity` and `time` (intake date, used by FIFO/LIFO). Returns the batch
	identifiers in the order the legacy `getResourcesForWarehouseProductAndAlgorithm`
	would consume them. Unknown algorithms fall back to FIFO
	(`WarehouseAlgorithm.parseString`, WarehouseAlgorithm.java:38-48).
	"""
	keys = _SEARCH_ORDERS[normalise_algorithm(algorithm)]
	ordered = sorted(resources, key=lambda resource: _sort_key(resource, keys))
	return tuple(str(resource["batch"]) for resource in ordered)
