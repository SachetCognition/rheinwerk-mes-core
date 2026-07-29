"""`Work Order` document gate refusing illegal `exec_state` transitions (URS-W1-002).

Registered as a `validate` doc_event in `hooks.py`: the anchor DocType is never forked, so
the transition set lives here and in `order_state`, layered over the anchor. The gate is a
hard stop — `frappe.throw` aborts the save, mirroring the legacy
`StateTransitionNotAlloweException` rather than a dismissable warning.
"""

from __future__ import annotations

import frappe
from frappe import _

from rheinwerk_mes.execution_gating.order_state import (
	EXEC_STATE_FIELD,
	LEGAL_TRANSITIONS,
	can_change_to,
	refusal_message,
	unknown_state_message,
)

REFUSAL_TITLE = "Übergang nicht zulässig"


def enforce_legal_transition(doc, method: str | None = None) -> None:
	"""Refuse any `exec_state` change that is not in the legal transition set."""
	target = doc.get(EXEC_STATE_FIELD)
	if not target:
		return

	if target not in LEGAL_TRANSITIONS:
		frappe.throw(unknown_state_message(target, _), title=_(REFUSAL_TITLE))

	previous = doc.get_doc_before_save()
	source = previous.get(EXEC_STATE_FIELD) if previous else None
	if not source or source == target:
		return

	if not can_change_to(source, target):
		frappe.throw(refusal_message(source, target, _), title=_(REFUSAL_TITLE))
