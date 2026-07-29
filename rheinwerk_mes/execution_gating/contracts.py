"""Completion-gate parity entrypoint for the characterisation harness (URS-W1-007).

This module owns `ENTRYPOINTS["order_completion"]` of the W0 characterisation harness
(`tests/characterisation/api.py`): with it in place, `CHAR-ORDER-COMPLETE-01` stops
running against the fixture-encoded legacy rule and executes against production code with
the same fixtures and no test change (URS-W1-007 AC-3).

`evaluate_order_completion` is a **pure function over a plain mapping** — no Frappe site
needed — and returns the *legacy Qcadoo message keys* so parity stays machine-checkable.
The German-first operator wording is built in `gates.py` from the same verdict.

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/
OrderStateValidationService.java:54-63` (`validationOnCompleted`), with the required-field
loop at `:64-72` (`checkRequired`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: Qcadoo message key raised once per null required field (`checkRequired`, :64-72).
FIELD_REQUIRED = "orders.order.orderStates.fieldRequired"

#: Qcadoo message key for a recorded output of exactly zero (`validationOnCompleted`).
DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO = "orders.order.orderStates.doneQuantityMustBeGreaterThanZero"

#: `validationOnCompleted` required fields, in declaration order (:54-56).
COMPLETION_REQUIRED_FIELDS: tuple[str, ...] = ("date_to", "date_from", "done_quantity")


@dataclass(frozen=True)
class Verdict:
	"""Outcome of a gate evaluation — the shape `tests/characterisation/api.py` compares.

	`errors` carries the legacy Qcadoo message keys in the order the legacy code raises
	them, so a contract can compare them verbatim against its fixture.
	"""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


def missing_fields(
	order: Mapping[str, Any], required: Sequence[str] = COMPLETION_REQUIRED_FIELDS
) -> tuple[str, ...]:
	"""Required fields that are null on `order` (`checkRequired`, :64-72)."""
	return tuple(name for name in required if order.get(name) is None)


def evaluate_order_completion(order: Mapping[str, Any]) -> Verdict:
	"""Completion gate: execution dates required, recorded output must exceed zero.

	Baseline `validationOnCompleted` (:54-63): dateTo, dateFrom and doneQuantity are
	required — one `fieldRequired` per null field, in declaration order — and a
	doneQuantity comparing equal to zero adds
	`orders.order.orderStates.doneQuantityMustBeGreaterThanZero`. The legacy suppression of
	that second error under the `ziepiwowarski` plugin is kept for fixture parity; the
	Rheinwerk estate never ships that plugin, so the flag defaults to false.
	"""
	errors = [FIELD_REQUIRED for _ in missing_fields(order)]
	done_quantity = order.get("done_quantity")
	plugin_enabled = bool(order.get("plugin_ziepiwowarski_enabled", False))
	if done_quantity is not None and float(done_quantity) == 0 and not plugin_enabled:
		errors.append(DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO)
	return Verdict(allowed=not errors, errors=tuple(errors))
