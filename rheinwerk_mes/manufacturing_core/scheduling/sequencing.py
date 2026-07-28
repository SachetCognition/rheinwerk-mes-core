"""Sequencing a line schedule (W3-2 · URS-W3-005, URS-W3-006, URS-W3-007).

Given the orders a planner put on a line, their TJ/TPZ norms and the line's changeover
norms, this module computes the schedule's start/end times. It is the norm/slot-based
sequencer URS-W3-009 fences: order sequence is the planner's, never an optimiser's
(`docs/decisions/DEC-W3-009-optimiser-build-vs-buy.md`).

Pure functions over plain mappings and `datetime` — no Frappe import, so both the parity
contracts and the offline acceptance cases can exercise the arithmetic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .changeover import changeover_minutes
from .realization_time import OperationRealization, order_realization


@dataclass(frozen=True)
class ScheduledOperation:
	"""One routed operation inside a scheduled order."""

	operation: str
	workstation: str | None
	sequence: int
	quantity: float
	tpz_min: int
	tj_min_per_unit: float
	setup_min: int
	run_min: int
	duration_min: int
	planned_start: datetime
	planned_end: datetime


@dataclass(frozen=True)
class ScheduledOrder:
	"""One order's place in the line sequence."""

	work_order: str
	production_item: str
	quantity: float
	sequence: int
	realization_min: int
	changeover_min: int
	changeover_note: str | None
	planned_start: datetime
	planned_end: datetime
	operations: tuple[ScheduledOperation, ...] = field(default_factory=tuple)


def _operations(
	realizations: Sequence[OperationRealization], start: datetime, quantity: float
) -> tuple[tuple[ScheduledOperation, ...], datetime]:
	"""Place a sequential routing's operations back to back from `start`."""
	placed: list[ScheduledOperation] = []
	cursor = start
	for index, realization in enumerate(realizations, start=1):
		end = cursor + timedelta(minutes=realization.duration_min)
		placed.append(
			ScheduledOperation(
				operation=realization.operation,
				workstation=realization.workstation,
				sequence=index * 10,
				quantity=quantity,
				tpz_min=realization.tpz_min,
				tj_min_per_unit=realization.tj_min_per_unit,
				setup_min=realization.setup_min,
				run_min=realization.run_min,
				duration_min=realization.duration_min,
				planned_start=cursor,
				planned_end=end,
			)
		)
		cursor = end
	return tuple(placed), cursor


def sequence_line(
	orders: Sequence[Mapping[str, Any]],
	start: datetime,
	*,
	changeover_norms: Sequence[Mapping[str, Any]] = (),
	production_line: str | None = None,
) -> tuple[ScheduledOrder, ...]:
	"""Sequence `orders` on one line from `start`.

	Each order mapping carries `work_order`, `production_item`, `quantity` and its routed
	`norms` (TJ/TPZ per operation, in routing order). Between two orders the matching line
	changeover norm is inserted; the first order of a schedule has no predecessor and
	therefore no changeover.
	"""
	scheduled: list[ScheduledOrder] = []
	cursor = start
	previous_item: str | None = None

	for position, order in enumerate(orders, start=1):
		item = str(order.get("production_item") or "")
		quantity = float(order.get("quantity") or 0)
		realizations, total = order_realization(order.get("norms") or (), quantity)

		minutes, note = (0, None)
		if previous_item is not None:
			minutes, note = changeover_minutes(changeover_norms, previous_item, item, production_line)
			cursor = cursor + timedelta(minutes=minutes)

		operations, end = _operations(realizations, cursor, quantity)
		scheduled.append(
			ScheduledOrder(
				work_order=str(order.get("work_order") or ""),
				production_item=item,
				quantity=quantity,
				sequence=position * 10,
				realization_min=total,
				changeover_min=minutes,
				changeover_note=note,
				planned_start=cursor,
				planned_end=end,
				operations=operations,
			)
		)
		cursor = end
		previous_item = item

	return tuple(scheduled)
