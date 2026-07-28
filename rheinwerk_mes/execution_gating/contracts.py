"""Order-gating parity entrypoints for the W0 characterisation harness (W1-2).

This module owns the two handover entrypoints listed in `tests/characterisation/api.py`
(`ENTRYPOINTS["order_acceptance"]` / `["order_completion"]`). With them in place,
`CHAR-ORDER-ACCEPT-01` and `CHAR-ORDER-COMPLETE-01` stop running against the
fixture-encoded legacy rule and execute against production code with the same fixtures
and no test change.

Both functions are **pure functions over plain mappings** (no Frappe site needed) so the
offline characterisation suite can call them, and they return the *legacy Qcadoo message
keys* so parity stays machine-checkable — the German-first operator messages are built by
`gates.py`, which feeds the same rules from the anchor Work Order document.

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/states/
OrderStateValidationService.java:44-47` (`validationOnAccepted`) and `:54-63`
(`validationOnCompleted`), with the required-field loop at `:64-72` (`checkRequired`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: Qcadoo message key raised once per null required field (`checkRequired`, :64-72).
FIELD_REQUIRED = "orders.order.orderStates.fieldRequired"

#: Qcadoo message key for a recorded output of exactly zero (`validationOnCompleted`).
DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO = "orders.order.orderStates.doneQuantityMustBeGreaterThanZero"

#: Qcadoo message key for an end date that is not after the start date
#: (`OrderStateService.checkOrderDates`, OrderStateService.java:47-59).
DATES_ORDER_OVERDUE = "orders.validate.global.error.datesOrder.overdue"

#: Message key raised when an expired batch is issued — the estate's own key: Plant A has
#: none, because it never refuses (URS-W1-030 divergence).
BATCH_EXPIRED = "rheinwerk.warehouse.issue.batchExpired"

#: `validationOnAccepted` required references, in declaration order (:44-47).
ACCEPTANCE_REQUIRED_FIELDS: tuple[str, ...] = ("date_to", "date_from", "production_line", "technology")

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


def missing_fields(order: Mapping[str, Any], required: Sequence[str]) -> tuple[str, ...]:
	"""Required fields that are null on `order` (`checkRequired`, :64-72)."""
	return tuple(name for name in required if order.get(name) is None)


def evaluate_order_acceptance(order: Mapping[str, Any]) -> Verdict:
	"""Acceptance gate (URS-W1-005): dates, production line and recipe are required.

	Baseline `validationOnAccepted` (:44-47) refuses the transition to *accepted* with
	`orders.order.orderStates.fieldRequired` for every null field among dateTo, dateFrom,
	productionLine and technology.

	Date consistency (`OrderStateService.checkOrderDates`, :47-59) is the second half of
	URS-W1-005 AC-2: when both dates are present and the end date is not *after* the start
	date, the legacy code adds `orders.validate.global.error.datesOrder.overdue`. It is
	appended after the required-field errors, matching the legacy evaluation order (the
	required-field validator runs in the earlier state-change phase).
	"""
	errors = [FIELD_REQUIRED for _ in missing_fields(order, ACCEPTANCE_REQUIRED_FIELDS)]
	if _dates_inconsistent(order.get("date_from"), order.get("date_to")):
		errors.append(DATES_ORDER_OVERDUE)
	return Verdict(allowed=not errors, errors=tuple(errors))


def evaluate_order_completion(order: Mapping[str, Any]) -> Verdict:
	"""Completion gate (URS-W1-007): dates required, recorded output must exceed zero.

	Baseline `validationOnCompleted` (:54-63): dateTo, dateFrom and doneQuantity are
	required; a doneQuantity comparing equal to zero adds
	`orders.order.orderStates.doneQuantityMustBeGreaterThanZero`. The legacy suppression
	of that second error under the `ziepiwowarski` plugin is kept for fixture parity — the
	Rheinwerk estate never ships that plugin, so the flag defaults to false.
	"""
	errors = [FIELD_REQUIRED for _ in missing_fields(order, COMPLETION_REQUIRED_FIELDS)]
	done_quantity = order.get("done_quantity")
	plugin_enabled = bool(order.get("plugin_ziepiwowarski_enabled", False))
	if done_quantity is not None and float(done_quantity) == 0 and not plugin_enabled:
		errors.append(DONE_QUANTITY_MUST_BE_GREATER_THAN_ZERO)
	return Verdict(allowed=not errors, errors=tuple(errors))


def _dates_inconsistent(date_from: Any, date_to: Any) -> bool:
	"""True when both dates are known and the end date is not after the start date."""
	if date_from is None or date_to is None:
		return False
	return _comparable(date_to) <= _comparable(date_from)


def _comparable(value: Any) -> Any:
	"""Normalise a German-first `DD.MM.YYYY` string or a date/datetime for comparison."""
	from datetime import date, datetime

	if isinstance(value, datetime):
		return value
	if isinstance(value, date):
		return datetime(value.year, value.month, value.day)
	text = str(value).strip()
	if "." in text:
		day, month, year = (int(part) for part in text.split(" ")[0].split("."))
		return datetime(year, month, day)
	return datetime.fromisoformat(text)


def evaluate_expired_issue(issue: Mapping[str, Any]) -> Verdict:
	"""Expiry policy on issuing stock — the estate refuses an expired batch (URS-W1-030).

	This is the pure-function form of the policy the site enforces in `expiry.py` (posting)
	and `allocation.py` (automatic allocation), exposed as the `expired_issue` contract
	entrypoint so the divergence from Plant A is measured rather than asserted in prose:
	`CHAR-EXPIRY-ISSUE-01` pins the legacy verdict (expired stock issuable) and this
	function refuses it, which the harness classifies as the signed-off divergence recorded
	in `docs/decisions/DEC-W1-030-expiry-policy.md`.

	`issue` carries `batch`, `expiration_date` and `posting_date` (both DD.MM.YYYY) and
	`quantity`.
	"""
	expiry = _comparable(issue["expiration_date"])
	posting = _comparable(issue["posting_date"])
	if expiry < posting:
		return Verdict(allowed=False, errors=(BATCH_EXPIRED,))
	return Verdict(allowed=True)
