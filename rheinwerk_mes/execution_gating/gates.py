"""Execution-gating hooks on the production-order state machine (W1-2).

Three gates are registered through the `rheinwerk_exec_state_gates` hook documented in
`docs/design/W1-exec-state.md` §4 — the state machine itself is never edited:

| Gate | URS | Transition | Legacy baseline (`SachetCognition/Chem_mes@master`) |
|---|---|---|---|
| `acceptance_gate` | URS-W1-005 | * → Accepted | `OrderStateValidationService.java:44-47`, `OrderStateService.java:47-59` |
| `recipe_accepted_gate` | URS-W1-006 | * → Accepted | Qcadoo orders reference accepted technologies (CDM-04) |
| `completion_gate` | URS-W1-007 | * → Completed | `OrderStateValidationService.java:54-63` |

Every gate judges only (no posting, per the gate contract), refuses through a German-first
hard-gate message naming **rule**, **record** and **resolution** (design skill
§"Hard gates look hard" — the state machine raises the collected messages as one modal,
never a toast) and writes an immutable `Execution Gate Log` refusal row (URS-W1-033).

The parity rules themselves live in `contracts.py` as pure functions over plain mappings
so the W0 characterisation harness executes the very same code (CHAR-ORDER-ACCEPT-01 /
CHAR-ORDER-COMPLETE-01); these gates only map the anchor document onto that mapping and
translate the verdict for the operator.
"""

from __future__ import annotations

from typing import Any

from frappe import _
from frappe.utils import flt, formatdate, strip_html

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.execution_gating.contracts import (
	ACCEPTANCE_REQUIRED_FIELDS,
	COMPLETION_REQUIRED_FIELDS,
	evaluate_order_acceptance,
	evaluate_order_completion,
	missing_fields,
)

ACCEPTED = "Accepted"
IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
DECLINED = "Declined"
ABANDONED = "Abandoned"

#: Canonical field mapping (CDM-02): Qcadoo order field → anchor `Work Order` fieldname.
ANCHOR_FIELDS: dict[str, str] = {
	"date_from": "planned_start_date",
	"date_to": "planned_end_date",
	"production_line": "production_line",
	"technology": "bom_no",
	"done_quantity": "produced_qty",
}

#: German-first labels of the gated fields, for the refusal modal.
FIELD_LABELS: dict[str, str] = {
	"date_from": "Geplanter Starttermin",
	"date_to": "Geplanter Endtermin",
	"production_line": "Fertigungslinie",
	"technology": "Rezept (Stückliste)",
	"done_quantity": "Erfasste Ausbringung",
}


# --------------------------------------------------------------------------------------
# Presentation helpers
# --------------------------------------------------------------------------------------


def hard_gate_message(rule: str, record: str, resolution: str) -> str:
	"""Compose a hard-gate refusal naming rule, record and resolution (design skill)."""
	return "<br>".join(
		[
			_("<b>Regel:</b> {0}").format(rule),
			_("<b>Datensatz:</b> {0}").format(record),
			_("<b>Behebung:</b> {0}").format(resolution),
		]
	)


def kg(value: Any) -> str:
	"""German-first mass rendering: decimal comma, three decimals trimmed, unit kg."""
	text = f"{flt(value):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


def _labels(names: tuple[str, ...]) -> str:
	return ", ".join(_(FIELD_LABELS[name]) for name in names)


# --------------------------------------------------------------------------------------
# Document → contract mapping
# --------------------------------------------------------------------------------------


def order_mapping(doc: Any) -> dict[str, Any]:
	"""Project the anchor Work Order onto the Qcadoo order mapping the contracts consume.

	`produced_qty` is mapped to `done_quantity` as-is: the anchor initialises it to 0, which
	is exactly the legacy "reported nothing" case the completion gate refuses. An unset
	quantity (None) keeps the legacy required-field refusal.
	"""
	mapped = {key: doc.get(fieldname) for key, fieldname in ANCHOR_FIELDS.items()}
	return {key: (value if value != "" else None) for key, value in mapped.items()}


# --------------------------------------------------------------------------------------
# Gates (registered in hooks.py, in this order)
# --------------------------------------------------------------------------------------


def acceptance_gate(context: Any) -> None:
	"""Accepting an order needs both planned dates, a production line and a recipe.

	URS-W1-005 · TC-W1-006. Baseline `OrderStateValidationService.validationOnAccepted`
	(:44-47) for the required references and `OrderStateService.checkOrderDates` (:47-59)
	for the date-range consistency (end must be *after* start).
	"""
	if context.to_state != ACCEPTED:
		return
	order = order_mapping(context.doc)
	verdict = evaluate_order_acceptance(order)
	if verdict.allowed:
		return

	missing = missing_fields(order, ACCEPTANCE_REQUIRED_FIELDS)
	if missing:
		_refuse(
			context,
			gate="acceptance_gate",
			rule=_("Annahme erfordert Starttermin, Endtermin, Fertigungslinie und Rezeptreferenz."),
			record=_("Auftrag {0} — fehlende Angaben: {1}").format(context.doc.name, _labels(missing)),
			resolution=_("Fehlende Felder im Fertigungsauftrag ergänzen und Annahme erneut auslösen."),
		)
	if len(verdict.errors) > len(missing):
		_refuse(
			context,
			gate="acceptance_gate",
			rule=_("Der Endtermin muss nach dem Starttermin liegen."),
			record=_("Auftrag {0} — Start {1}, Ende {2}").format(
				context.doc.name,
				_de_date(order.get("date_from")),
				_de_date(order.get("date_to")),
			),
			resolution=_("Terminrahmen korrigieren, sodass das Ende nach dem Start liegt."),
		)


def recipe_accepted_gate(context: Any) -> None:
	"""An order may only be accepted against an Accepted recipe.

	URS-W1-006 · TC-W1-007. Qcadoo orders reference accepted technologies; the canonical
	reading is CDM-04 ("orders may only reference Accepted recipes — gate in CDM-02
	accept"). Uses the governance API `recipe_isa88.governance.gov_state` (W1-4).
	"""
	if context.to_state != ACCEPTED:
		return
	recipe = context.doc.get("bom_no")
	if not recipe:
		return  # the acceptance gate already refuses a missing recipe reference

	from rheinwerk_mes.recipe_isa88 import governance

	state = governance.gov_state(recipe)
	if state == governance.ACCEPTED:
		return
	_refuse(
		context,
		gate="recipe_accepted_gate",
		rule=_("Fertigungsaufträge dürfen nur freigegebene Rezepte verwenden (Freigabestatus Accepted)."),
		record=_("Auftrag {0} — Rezept {1}, Freigabestatus {2}").format(
			context.doc.name,
			recipe,
			_(state) if state else _("nicht geführt"),
		),
		resolution=_("Rezept über die Rezeptlenkung freigeben oder ein freigegebenes Rezept auswählen."),
	)


def completion_gate(context: Any) -> None:
	"""Completing an order needs a recorded output above zero and the execution dates.

	URS-W1-007 · TC-W1-008. Baseline `OrderStateValidationService.validationOnCompleted`
	(:54-63). The complementary shortfall rule (produced < ordered needs a reason) is the
	state machine's own `shortfall_gate` (URS-W1-004) and stays there.
	"""
	if context.to_state != COMPLETED:
		return
	order = order_mapping(context.doc)
	verdict = evaluate_order_completion(order)
	if verdict.allowed:
		return

	missing = missing_fields(order, COMPLETION_REQUIRED_FIELDS)
	if missing:
		_refuse(
			context,
			gate="completion_gate",
			rule=_("Abschluss erfordert Start- und Endtermin sowie eine erfasste Ausbringung."),
			record=_("Auftrag {0} — fehlende Angaben: {1}").format(context.doc.name, _labels(missing)),
			resolution=_("Termine pflegen und die Ausbringung über die Rückmeldung erfassen."),
		)
	if len(verdict.errors) > len(missing):
		_refuse(
			context,
			gate="completion_gate",
			rule=_("Ein Auftrag ohne erfasste Ausbringung kann nicht abgeschlossen werden."),
			record=_("Auftrag {0} — erfasste Ausbringung {1} von {2}").format(
				context.doc.name, kg(context.doc.get("produced_qty")), kg(context.doc.get("qty"))
			),
			resolution=_(
				"Ausbringung über Fertigungsbuchung bzw. Arbeitsgangrückmeldung erfassen "
				"oder den Auftrag abbrechen."
			),
		)


# --------------------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------------------


def _refuse(context: Any, *, gate: str, rule: str, record: str, resolution: str) -> None:
	"""Append the hard-gate message to the transition context and log the refusal."""
	context.refuse(hard_gate_message(rule, record, resolution))
	audit.log_refusal(
		gate=gate,
		rule=rule,
		document=context.doc,
		from_state=context.from_state,
		to_state=context.to_state,
		detail=strip_html(f"{record} — {resolution}"),
	)


def _de_date(value: Any) -> str:
	"""Render a date German-first (DD.MM.YYYY); empty when unset."""
	if not value:
		return _("nicht gesetzt")
	return formatdate(value, "dd.MM.yyyy")
