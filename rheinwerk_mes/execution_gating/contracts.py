"""Acceptance-gate parity rules — URS-W1-005 (AC-1, AC-2, AC-4).

This module is the **target implementation** behind the W0 characterisation contract
`CHAR-ORDER-ACCEPT-01`: the harness resolves
`rheinwerk_mes.execution_gating.contracts.evaluate_order_acceptance` (see
`tests/characterisation/api.py` § `ENTRYPOINTS`) and, once it exists, stops running its
fixture-encoded legacy rule and checks production code instead. The fixtures therefore
pin this code, which is the parity guarantee ADR-001 asks for.

Legacy baseline (semantics only, never ported), in `SachetCognition/Chem_mes@master`
under `mes-plugins/mes-plugins-orders/src/main/java/com/qcadoo/mes/orders/`:

* `states/OrderStateValidationService.java:44-47` (`validationOnAccepted` →
  `checkRequired` at `:64-72`) — dateTo, dateFrom, productionLine and technology are
  required, one `fieldRequired` error per null field, in declaration order.
* `states/OrderStateService.java:47-59` (`checkOrderDates`) — a planned range whose end
  is not *after* its start refuses the transition with `datesOrder.overdue`.

Orders are read as legacy-shaped mappings (`date_from`, `date_to`, `production_line`,
`technology`) so contract fixtures and the Frappe gate share one rule; the gate in
`acceptance_gate.py` maps the anchor `Work Order` onto that shape and turns the returned
message keys into the German-first modal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

#: Qcadoo message keys, kept verbatim so refusal reasons stay comparable across the
#: migration (`OrderStateValidationService.java:69`, `OrderStateService.java:57`).
FIELD_REQUIRED = "orders.order.orderStates.fieldRequired"
DATES_ORDER_OVERDUE = "orders.validate.global.error.datesOrder.overdue"


@dataclass(frozen=True)
class Verdict:
	"""Outcome of the acceptance gate — `errors` holds legacy keys in refusal order."""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RequiredField:
	"""One required field: its legacy name, its canonical anchor field and its label."""

	legacy: str
	canonical: str
	label: str


#: Verbatim from the legacy `Arrays.asList(DATE_TO, DATE_FROM, PRODUCTION_LINE, TECHNOLOGY)`;
#: the order is behaviour, because it is the order the refusals are raised in. Canonical
#: names are the anchor `Work Order` fields per CDM-02 / CDM-04 (`bom_no` = recipe).
REQUIRED_FIELDS: tuple[RequiredField, ...] = (
	RequiredField("date_to", "planned_end_date", "Geplantes Enddatum"),
	RequiredField("date_from", "planned_start_date", "Geplantes Startdatum"),
	RequiredField("production_line", "production_line", "Fertigungslinie"),
	RequiredField("technology", "bom_no", "Rezeptur"),
)

DE_DATE_FORMAT = "%d.%m.%Y"


def parse_date(value: Any) -> datetime | None:
	"""Read a planned date: `date`/`datetime`, German-first `DD.MM.YYYY` or ISO text.

	The plant thinks in DD.MM.YYYY (design skill § "Content and language") and the
	characterisation fixtures are written that way, while Frappe hands over `date`,
	`datetime` or ISO strings. Unparseable values are treated as absent, which lets the
	required-field rule — not the range rule — own the refusal.
	"""
	if value is None or value == "":
		return None
	if isinstance(value, datetime):
		return value
	if isinstance(value, date):
		return datetime(value.year, value.month, value.day)
	text = str(value).strip()
	try:
		return datetime.strptime(text, DE_DATE_FORMAT)
	except ValueError:
		pass
	try:
		return datetime.fromisoformat(text)
	except ValueError:
		return None


def format_date(value: Any) -> str:
	"""Render a planned date German-first (DD.MM.YYYY); unparseable values pass through."""
	parsed = parse_date(value)
	return parsed.strftime(DE_DATE_FORMAT) if parsed else str(value)


def missing_fields(order: Mapping[str, Any]) -> tuple[RequiredField, ...]:
	"""Required fields the order does not carry, in legacy declaration order.

	Baseline: `OrderStateValidationService.java:64-72` (`checkRequired`) — a field is
	missing when its value is null; an unset Frappe Link or Date field carries `""`
	rather than `None`, so emptiness rather than nullity is the test.
	"""
	return tuple(spec for spec in REQUIRED_FIELDS if not order.get(spec.legacy))


def has_inconsistent_date_range(order: Mapping[str, Any]) -> bool:
	"""True when both planned dates are set and the end is not after the start.

	Baseline: `OrderStateService.java:47-59` — the refusal is raised unless
	`dateTo.after(dateFrom)`, so an end equal to the start is refused too.
	"""
	date_from = parse_date(order.get("date_from"))
	date_to = parse_date(order.get("date_to"))
	if date_from is None or date_to is None:
		return False
	return date_to <= date_from


def evaluate_order_acceptance(order: Mapping[str, Any]) -> Verdict:
	"""Pending→Accepted gate: required fields first, then planned-range consistency.

	Baseline: `OrderStateValidationService.java:44-47` followed by
	`OrderStateService.java:47-59`. The keys are returned in refusal order so the
	characterisation fixtures pin both the verdict and the sequence.
	"""
	errors = [FIELD_REQUIRED for _spec in missing_fields(order)]
	if has_inconsistent_date_range(order):
		errors.append(DATES_ORDER_OVERDUE)
	return Verdict(allowed=not errors, errors=tuple(errors))
