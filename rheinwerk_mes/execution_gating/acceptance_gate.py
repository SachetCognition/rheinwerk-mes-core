"""Acceptance gate on the anchor Work Order — URS-W1-005 (AC-1…AC-3), TC-W1-006.

Registered as an `exec_state` gate (hooks key `rheinwerk_exec_state_gates`), so the
Pending→Accepted transition — from the Desk workflow bar or from any server-side caller
— passes through `acceptance_gate()`. The rule itself lives in `contracts.py`, which is
also the characterisation entrypoint (URS-W1-005 AC-4): one rule, two consumers.

Refusals follow the design skill § "Interaction rules — Hard gates look hard": the
message names the rule, the record and what resolves it, the state machine renders it as
a modal (never a toast), and every refusal is logged with the acting user.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.execution_gating.contracts import (
	REQUIRED_FIELDS,
	format_date,
	has_inconsistent_date_range,
	missing_fields,
)

#: `exec_state` vocabulary value this gate guards (URS-W1-001, design skill § "State
#: names are law"). The gate is a no-op for every other target state.
ACCEPTED = "Accepted"

#: Rule names as they appear in the refusal modal and the log (URS-W1-005).
RULE_REQUIRED_FIELDS = "Annahme-Gate: Pflichtangaben"
RULE_DATE_RANGE = "Annahme-Gate: Datumsfolge"

LOGGER_NAME = "rheinwerk_mes.execution_gating"


def legacy_view(doc: Any) -> dict[str, Any]:
	"""Map an anchor `Work Order` onto the legacy field names the rule reads.

	Keeping the mapping here — and the rule legacy-shaped — is what lets the Qcadoo
	characterisation fixtures and the production gate share a single implementation.
	"""
	view: dict[str, Any] = {"number": doc.name}
	for spec in REQUIRED_FIELDS:
		view[spec.legacy] = doc.get(spec.canonical)
	return view


def refusals(doc: Any) -> list[str]:
	"""German-first refusal messages for accepting `doc`; empty when the gate passes."""
	order = legacy_view(doc)
	messages = [
		_(
			"{0}: Auftrag {1} hat keine Angabe im Feld „{2}“. "
			"Feld ausfüllen und die Annahme erneut ausführen."
		).format(RULE_REQUIRED_FIELDS, doc.name, _(spec.label))
		for spec in missing_fields(order)
	]
	if has_inconsistent_date_range(order):
		messages.append(
			_(
				"{0}: Auftrag {1} endet am {2}, also nicht nach dem geplanten Start am {3}. "
				"Enddatum nach dem Startdatum setzen und die Annahme erneut ausführen."
			).format(
				RULE_DATE_RANGE,
				doc.name,
				format_date(order.get("date_to")),
				format_date(order.get("date_from")),
			)
		)
	return messages


def acceptance_gate(context: Any) -> None:
	"""Refuse Pending→Accepted unless dates, production line and recipe are consistent.

	`context` is the `TransitionContext` of the `exec_state` machine; refusals are
	appended to it so the machine presents them together as one modal.
	"""
	if context.to_state != ACCEPTED:
		return

	messages = refusals(context.doc)
	if not messages:
		return

	for message in messages:
		context.refuse(message)
	log_refusal(context, messages)


def log_refusal(context: Any, messages: list[str]) -> None:
	"""Log a gate refusal — compliance moments are never only presented (TC-W1-036)."""
	order = legacy_view(context.doc)
	frappe.logger(LOGGER_NAME, allow_site=True).warning(
		{
			"gate": "URS-W1-005 acceptance gate",
			"work_order": context.doc.name,
			"from_state": context.from_state,
			"to_state": context.to_state,
			"missing_fields": [spec.canonical for spec in missing_fields(order)],
			"inconsistent_date_range": has_inconsistent_date_range(order),
			"user": frappe.session.user,
			"messages": messages,
		}
	)
