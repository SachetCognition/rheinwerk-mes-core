"""Completion gate on the production-order state machine (URS-W1-007).

The gate refuses the In Progress→Completed transition of the anchor `Work Order` when the
recorded output is zero or when a required execution date is missing, matching Qcadoo
(`OrderStateValidationService.java:54-63`). It **judges only** — no posting, no field
mutation — and refuses through a German-first hard-gate modal naming **rule**, **record**
and **resolution** (design skill §"Hard gates look hard"; the collected refusals are raised
as one modal, never a toast).

The parity rule itself lives in `contracts.py` as a pure function over a plain mapping, so
the W0 characterisation harness executes the very same code (`CHAR-ORDER-COMPLETE-01`);
this module only maps the anchor document onto that mapping and translates the verdict for
the operator.

Wiring: `hooks.py` registers `completion_gate` as a `Work Order` `validate` doc_event, so
every path into the completed state passes it — the anchor is never forked. The state
field is read as `exec_state` when the W1 workflow (URS-W1-001) is installed and as the
anchor-derived `status` otherwise (URS-W1-004: no unqualified "status" is written here).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.execution_gating.contracts import (
	evaluate_order_completion,
	missing_fields,
)

#: Completed in the W1 `exec_state` workflow and in the anchor's derived status alike.
COMPLETED = "Completed"

#: Canonical field mapping (CDM-02): Qcadoo order field → anchor `Work Order` fieldname.
ANCHOR_FIELDS: dict[str, str] = {
	"date_from": "planned_start_date",
	"date_to": "planned_end_date",
	"done_quantity": "produced_qty",
}

#: German-first labels of the gated fields, for the refusal modal (URS-W1-034).
FIELD_LABELS: dict[str, str] = {
	"date_from": "Geplanter Starttermin",
	"date_to": "Geplanter Endtermin",
	"done_quantity": "Erfasste Ausbringung",
}


def translate(text: str) -> str:
	"""`frappe._` when a site is bound, the German source string otherwise.

	Gate texts are German-first at the source (URS-W1-034), so the untranslated fallback
	keeps them readable for the offline suite, which asserts refusal wording without a site.
	"""
	return _(text) if getattr(frappe.local, "site", None) else text


@dataclass(frozen=True)
class GateRefusal:
	"""One hard-gate refusal, named the way the design skill requires."""

	gate: str
	rule: str
	record: str
	resolution: str

	def as_message(self) -> str:
		return "<br>".join(
			[
				translate("<b>Regel:</b> {0}").format(self.rule),
				translate("<b>Datensatz:</b> {0}").format(self.record),
				translate("<b>Behebung:</b> {0}").format(self.resolution),
			]
		)


def kg(value: Any) -> str:
	"""German-first mass rendering: decimal comma, trailing zeros trimmed, unit kg."""
	text = f"{float(value or 0):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


def order_mapping(doc: Any) -> dict[str, Any]:
	"""Project the anchor Work Order onto the Qcadoo order mapping `contracts.py` consumes.

	`produced_qty` maps to `done_quantity` as-is: the anchor initialises it to 0, which is
	exactly the legacy "reported nothing" case the gate refuses. An unset value (None)
	keeps the legacy required-field refusal.
	"""
	mapped = {key: doc.get(fieldname) for key, fieldname in ANCHOR_FIELDS.items()}
	return {key: (value if value != "" else None) for key, value in mapped.items()}


def order_state(doc: Any) -> Any:
	"""The order's execution state: the W1 `exec_state` when installed, else the anchor status."""
	return doc.get("exec_state") or doc.get("status")


def entering_completed(doc: Any) -> bool:
	"""True when this save moves the order into the completed state.

	A document that is already completed is not re-gated, so corrections on a completed
	order (and the anchor's own status recalculations) do not raise the refusal twice.
	"""
	if order_state(doc) != COMPLETED:
		return False
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	return before is None or order_state(before) != COMPLETED


def completion_refusals(doc: Any) -> tuple[GateRefusal, ...]:
	"""Evaluate the completion gate for `doc`; empty when completion is allowed.

	URS-W1-007 · TC-W1-008. The verdict comes from the parity contract; the missing-field
	refusal and the zero-output refusal are reported separately so the modal names the
	rule that actually fired.
	"""
	order = order_mapping(doc)
	verdict = evaluate_order_completion(order)
	if verdict.allowed:
		return ()

	refusals: list[GateRefusal] = []
	missing = missing_fields(order)
	if missing:
		refusals.append(
			GateRefusal(
				gate="completion_gate",
				rule=translate("Abschluss erfordert Start- und Endtermin sowie eine erfasste Ausbringung."),
				record=translate("Auftrag {0} — fehlende Angaben: {1}").format(
					doc.get("name"), ", ".join(translate(FIELD_LABELS[name]) for name in missing)
				),
				resolution=translate("Termine pflegen und die Ausbringung über die Rückmeldung erfassen."),
			)
		)
	if len(verdict.errors) > len(missing):
		refusals.append(
			GateRefusal(
				gate="completion_gate",
				rule=translate("Ein Auftrag ohne erfasste Ausbringung kann nicht abgeschlossen werden."),
				record=translate("Auftrag {0} — erfasste Ausbringung {1} von {2}").format(
					doc.get("name"), kg(doc.get("produced_qty")), kg(doc.get("qty"))
				),
				resolution=translate(
					"Ausbringung über Fertigungsbuchung bzw. Arbeitsgangrückmeldung erfassen "
					"oder den Auftrag abbrechen."
				),
			)
		)
	return tuple(refusals)


def completion_gate(doc: Any, method: str | None = None) -> None:
	"""`Work Order` doc_event: refuse the transition into Completed without recorded output."""
	if not entering_completed(doc):
		return
	refusals = completion_refusals(doc)
	if not refusals:
		return
	frappe.throw(
		"<br><br>".join(refusal.as_message() for refusal in refusals),
		title=translate("Abschluss abgelehnt"),
	)
