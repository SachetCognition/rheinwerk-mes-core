"""Realization times from TJ/TPZ norms (W3-2 · URS-W3-006).

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`
`mes-plugins/mes-plugins-production-scheduling/src/main/java/com/qcadoo/mes/
productionScheduling/OrderRealizationTimeServiceImpl.java:156-186`
(`evaluateOperationDurationOutOfCycles`) and `:82-141`
(`estimateOperationTimeConsumption`, the per-operation aggregation).

The legacy arithmetic, minute-exact:

1. cycles = the operation's runs; with `maxForWorkstation` the cycles are spread over the
   work centre's workstation count and, for a non-divisible TJ, rounded **up** to whole
   cycles (`RoundingMode.CEILING`, `:167-171`);
2. run time = `cycles × TJ × staffFactor` **truncated** to whole minutes — the legacy code
   calls `BigDecimal.intValue()` (`:176`), which drops the fraction, it does not round;
3. TPZ (setup) is added once per work centre with `maxForWorkstation`, else once per
   workstation (`:178-181`);
4. the optional "time for next operation" surcharge follows the same rule (`:183-186`).

TJ and TPZ are whole minutes in Qcadoo (`Integer` fields) while the Rheinwerk norms carry
TJ as minutes per kg — `norms.py` keeps that as a float and the truncation above is applied
to the product, exactly as the legacy code does.

Pure functions over plain mappings: no Frappe import, so the parity contract runs offline.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperationRealization:
	"""Realization time of one routed operation, in whole minutes."""

	operation: str
	workstation: str | None
	quantity: float
	tpz_min: int
	tj_min_per_unit: float
	setup_min: int
	run_min: int

	@property
	def duration_min(self) -> int:
		return self.setup_min + self.run_min


def _int_value(value: Any) -> int:
	"""`OrderRealizationTimeServiceImpl.getIntegerValue(:188-190)` — null becomes 0."""
	if value is None:
		return 0
	return int(value)


def operation_duration(
	quantity: float,
	tj_min_per_unit: float,
	tpz_min: float = 0,
	*,
	include_tpz: bool = True,
	workstations_count: int = 1,
	max_for_workstation: bool = True,
	tj_divisible: bool = True,
	staff_factor: float = 1.0,
	additional_time_min: float = 0,
	include_additional_time: bool = False,
) -> int:
	"""Whole minutes for one operation (`evaluateOperationDurationOutOfCycles`, :156-186)."""
	workstations = max(int(workstations_count or 1), 1)
	cycles = float(quantity or 0)
	if max_for_workstation:
		cycles = cycles / workstations
		if not tj_divisible:
			cycles = float(math.ceil(cycles))

	duration = int(cycles * float(tj_min_per_unit or 0) * float(staff_factor or 1))

	if include_tpz:
		tpz = _int_value(tpz_min)
		duration += tpz if max_for_workstation else tpz * workstations

	if include_additional_time:
		additional = _int_value(additional_time_min)
		duration += additional if max_for_workstation else additional * workstations

	return duration


def realize_operation(norm: Mapping[str, Any], quantity: float) -> OperationRealization:
	"""Split one norm's realization into its setup (TPZ) and run (TJ) halves."""
	include_tpz = bool(norm.get("include_tpz", True))
	workstations_count = int(norm.get("workstations_count") or 1)
	max_for_workstation = bool(norm.get("max_for_workstation", True))
	run_min = operation_duration(
		quantity,
		norm.get("tj_min_per_unit", 0),
		include_tpz=False,
		workstations_count=workstations_count,
		max_for_workstation=max_for_workstation,
		tj_divisible=bool(norm.get("tj_divisible", True)),
		staff_factor=float(norm.get("staff_factor") or 1),
	)
	setup_min = 0
	if include_tpz:
		tpz = _int_value(norm.get("tpz_min", 0))
		setup_min = tpz if max_for_workstation else tpz * max(workstations_count, 1)
	return OperationRealization(
		operation=str(norm.get("operation") or ""),
		workstation=norm.get("workstation"),
		quantity=float(quantity or 0),
		tpz_min=_int_value(norm.get("tpz_min", 0)),
		tj_min_per_unit=float(norm.get("tj_min_per_unit") or 0),
		setup_min=setup_min,
		run_min=run_min,
	)


def order_realization(
	norms: Sequence[Mapping[str, Any]], quantity: float
) -> tuple[tuple[OperationRealization, ...], int]:
	"""Per-operation realizations and the order total for a **sequential** routing.

	URS-W3-006 AC-1: MIX (TPZ 30, TJ 0.6) and FILL (TPZ 15, TJ 0.3) over 500 kg give
	330 + 165 = 495 min. Qcadoo's parallel-branch offset (`:95-125`) collapses to the plain
	sum for the routings the estate actually runs — every Rheinwerk routing is a chain
	(`docs/design/W3-finite-capacity.md`).
	"""
	realizations = tuple(realize_operation(norm, quantity) for norm in norms)
	return realizations, sum(item.duration_min for item in realizations)


def realization_time(inputs: Mapping[str, Any]) -> int:
	"""Parity entrypoint shape: one mapping in, whole minutes out (URS-W3-006 AC-2)."""
	if "operations" in inputs:
		_realizations, total = order_realization(inputs["operations"], inputs.get("quantity", 0))
		return total
	return operation_duration(
		inputs.get("quantity", 0),
		inputs.get("tj_min_per_unit", 0),
		inputs.get("tpz_min", 0),
		include_tpz=bool(inputs.get("include_tpz", True)),
		workstations_count=int(inputs.get("workstations_count") or 1),
		max_for_workstation=bool(inputs.get("max_for_workstation", True)),
		tj_divisible=bool(inputs.get("tj_divisible", True)),
		staff_factor=float(inputs.get("staff_factor") or 1),
		additional_time_min=inputs.get("additional_time_min", 0),
		include_additional_time=bool(inputs.get("include_additional_time", False)),
	)
