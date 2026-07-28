"""Quality gates on the W1 `exec_state` and the W2 `qa_state` machines (URS-W2-014/016).

Both gates are registered through the documented hook lists (`rheinwerk_exec_state_gates`,
`rheinwerk_qa_state_gates`); neither `manufacturing_core` nor `genealogy` is edited — see
`docs/design/W1-exec-state.md` §4 and `docs/design/W2-genealogy.md` §3.

| Gate | URS | Transition | Adopted anchor behaviour |
|---|---|---|---|
| `quality_inspection_gate` | URS-W2-014 | Work Order * → Completed | `quality_inspection_service.py:21-127` (QI required / not submitted / rejected), severity fixed to Stop |
| `rejected_inspection_gate` | URS-W2-016 | Batch * → Released | `quality_inspection.py:265-281` (rejected readings ⇒ rejected result) |

Gates judge only — they never post (gate contract). Every refusal is a German-first hard
gate naming **rule**, **record** and **resolution** and is written to the W1
`Execution Gate Log` through `rheinwerk_mes.execution_gating.audit`.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import strip_html

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.execution_gating.gates import COMPLETED, hard_gate_message
from rheinwerk_mes.genealogy import qa_state
from rheinwerk_mes.quality import inspections

#: Rule identifiers — the same string is shown in the modal and written to the gate log.
QI_REQUIRED_RULE = "QI-Pflichtprüfung"
QI_REJECTED_RULE = "QI-Ablehnung ohne Verwendungsentscheid"


def _record(*parts: str | None) -> str:
	return ", ".join(part for part in parts if part)


def quality_inspection_gate(context: Any) -> None:
	"""Completion needs an Accepted inspection for every produced batch (URS-W2-014).

	AC-1 (missing/unsubmitted) and AC-2 (Rejected) both refuse; the severity is fixed to
	Stop estate-wide (dossier §8.2 Q1 — signed off in URS-W2-014, never configurable).
	"""
	if context.to_state != COMPLETED:
		return
	order = context.doc.name
	for produced in inspections.produced_batches(order):
		batch, item = produced["batch"], produced["item"]
		template = inspections.template_for_item(item)
		if not template:
			continue
		record = _record(order, batch, template)
		if inspections.accepted_inspection(batch):
			continue
		# A batch already Released passed QA through the audited disposition path
		# (URS-W2-006 AC-2/AC-3) — the gate asks for QA evidence, not for a specific
		# document (decision D5, docs/design/W2-quality-coa.md).
		if frappe.db.get_value("Batch", batch, "qa_state") == qa_state.RELEASED:
			continue
		rejected = inspections.rejected_inspections(batch)
		if rejected:
			message = hard_gate_message(
				rule=_("{0}: die Prüfung {1} ist abgelehnt.").format(QI_REJECTED_RULE, rejected[0]["name"]),
				record=_record(record, rejected[0]["name"]),
				resolution=_(
					"Verwendungsentscheid der Charge erfassen (Sperren oder Nacharbeit); "
					"der Auftrag bleibt bis dahin gesperrt."
				),
			)
			rule = QI_REJECTED_RULE
		else:
			draft = inspections.open_inspection(batch)
			message = hard_gate_message(
				rule=_("{0}: für die Charge {1} liegt keine angenommene Prüfung vor.").format(
					QI_REQUIRED_RULE, batch
				)
				+ (_(" Die Prüfung {0} ist noch nicht gebucht.").format(draft) if draft else ""),
				record=record,
				resolution=_("Prüfung nach Vorlage {0} erfassen und annehmen.").format(template),
			)
			rule = QI_REQUIRED_RULE
		context.errors.append(message)
		audit.log_refusal(
			gate="quality_inspection_gate",
			rule=rule,
			document=context.doc,
			from_state=context.from_state,
			to_state=context.to_state,
			detail=strip_html(message.replace("<br>", " · ")),
		)


def rejected_inspection_gate(context: Any) -> None:
	"""A batch with an undispositioned Rejected inspection may not be released (URS-W2-016).

	The reverse route — Rejected ⇒ Blocked or rework — is the disposition action itself
	(`rheinwerk_mes.quality.disposition`), which records the decision on the inspection and
	then drives `qa_state` through the genealogy API.
	"""
	from rheinwerk_mes.quality import disposition

	if context.to_state != qa_state.RELEASED:
		return
	pending = [
		row["name"]
		for row in inspections.rejected_inspections(context.doc.name)
		if not disposition.is_dispositioned(row)
	]
	if not pending:
		return
	context.refuse(
		hard_gate_message(
			rule=_("{0}: abgelehnte Prüfung {1}.").format(QI_REJECTED_RULE, ", ".join(pending)),
			record=_record(context.doc.name, ", ".join(pending)),
			resolution=_("Verwendungsentscheid zur abgelehnten Prüfung erfassen."),
		)
	)
