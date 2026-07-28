"""Audit + immutable logging of every gated action (W1-2 · URS-W1-033).

Both halves of a gated action are logged to `Execution Gate Log`:

* **refusals** — written by the gates in `gates.py` the moment they refuse, naming the
  gate, the rule, the record, the user and the timestamp (TC-W1-036 step 1);
* **executed transitions** — written by `side_effects.on_work_order_update` from the
  `state_history` row the state machine just appended (URS-W1-033: transitions, not only
  refusals, are logged).

A refusal aborts the surrounding transaction (`frappe.throw` → the request rolls back),
which would take the audit row with it. The row is therefore *also* registered as an
after-rollback callback, mirroring how Frappe keeps its own `Error Log` entries alive
across a rolled-back request: the entry is re-inserted and committed once the rollback
completed. Inside the test suite (`frappe.flags.in_test`) the callback is not registered,
so the per-test rollback stays clean while the in-transaction row is still assertable.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

LOG_DOCTYPE = "Execution Gate Log"

REFUSED = "Abgelehnt"
EXECUTED = "Durchgeführt"


def _entry(
	*,
	gate: str,
	outcome: str,
	rule: str,
	reference_doctype: str,
	reference_name: str,
	from_state: str | None,
	to_state: str | None,
	detail: str | None,
	state_history_row: str | None = None,
) -> dict[str, Any]:
	return {
		"doctype": LOG_DOCTYPE,
		"gate": gate,
		"outcome": outcome,
		"rule": rule,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"from_state": from_state,
		"to_state": to_state,
		"detail": detail,
		"state_history_row": state_history_row,
		"logged_by": frappe.session.user,
		"logged_at": now_datetime(),
	}


def _insert(entry: dict[str, Any]) -> str:
	doc = frappe.get_doc(entry)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def _survive_rollback(entry: dict[str, Any]) -> None:
	"""Re-write the entry after the refusal rolled the request back, then commit it."""

	def rewrite() -> None:
		try:
			_insert(dict(entry))
			frappe.db.commit()
		except Exception:  # never let the audit path mask the refusal itself
			frappe.log_error(
				title=_("Protokolleintrag des Ausführungs-Gates konnte nicht geschrieben werden")
			)

	frappe.db.after_rollback.add(rewrite)


def log_refusal(
	*,
	gate: str,
	rule: str,
	document: Any,
	from_state: str | None = None,
	to_state: str | None = None,
	detail: str | None = None,
) -> str:
	"""Log a gate refusal against `document` (URS-W1-033 AC-1); returns the entry name."""
	entry = _entry(
		gate=gate,
		outcome=REFUSED,
		rule=rule,
		reference_doctype=document.doctype,
		reference_name=document.name,
		from_state=from_state,
		to_state=to_state,
		detail=detail,
	)
	name = _insert(entry)
	if not frappe.flags.in_test:
		_survive_rollback(entry)
	return name


def log_transition(
	*,
	gate: str,
	rule: str,
	document: Any,
	from_state: str | None,
	to_state: str | None,
	detail: str | None = None,
	state_history_row: str | None = None,
) -> str:
	"""Log an executed, gate-passing transition of `document` (URS-W1-033 AC-1)."""
	return _insert(
		_entry(
			gate=gate,
			outcome=EXECUTED,
			rule=rule,
			reference_doctype=document.doctype,
			reference_name=document.name,
			from_state=from_state,
			to_state=to_state,
			detail=detail,
			state_history_row=state_history_row,
		)
	)


def entries_for(reference_doctype: str, reference_name: str) -> list[dict[str, Any]]:
	"""Audit entries of one record, oldest first — the order's audit view (TC-W1-036)."""
	return frappe.get_all(
		LOG_DOCTYPE,
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=[
			"name",
			"gate",
			"outcome",
			"rule",
			"detail",
			"from_state",
			"to_state",
			"logged_by",
			"logged_at",
		],
		order_by="logged_at asc, creation asc",
	)
