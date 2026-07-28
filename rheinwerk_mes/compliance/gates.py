"""Signature gates on the four dispositive acts (DEC-W2-029 · URS-W2-029 AC-2).

Registered through the documented interception points — the `qa_state` gate hook and two
`doc_events` — so neither `genealogy`, `quality` nor `recipe_isa88` is edited.
"""

from __future__ import annotations

from typing import Any

import frappe

from rheinwerk_mes.compliance import esignature
from rheinwerk_mes.genealogy import contracts as batch_contracts
from rheinwerk_mes.recipe_isa88 import governance

QA_ACTS: dict[str, str] = {
	batch_contracts.RELEASED: esignature.ACT_QA_RELEASE,
	batch_contracts.BLOCKED: esignature.ACT_QA_BLOCK,
}


def qa_state_signature_gate(context: Any) -> None:
	"""`rheinwerk_qa_state_gates` — release and block need a signature; entry does not.

	A disposition driven by a document (the inspection that released the batch, the QA
	disposition that blocked it) may carry the signature on that document instead: the
	inspector signs the act once, where they perform it.
	"""
	act = QA_ACTS.get(context.to_state)
	if not act:
		return
	alternatives: list[tuple[str, str]] = []
	trigger = context.triggering_document
	if trigger and frappe.db.exists("Quality Inspection", trigger):
		alternatives.append(("Quality Inspection", trigger))
	esignature.require(
		context.doc,
		act,
		consumer=f"qa_state:{context.from_state}->{context.to_state}",
		alternatives=alternatives,
	)


def coa_issue_signature_gate(doc: Any, method: str | None = None) -> None:
	"""`CoA Certificate.before_insert` — the signer certifies the results (DEC-W2-029).

	The certificate does not exist yet when it must be signed, so the signature is taken
	against the inspection whose readings it publishes — which is also what the signer is
	certifying, and what the payload hash covers.
	"""
	inspection = frappe.get_doc("Quality Inspection", doc.quality_inspection)
	esignature.require(inspection, esignature.ACT_COA_ISSUE, consumer=f"coa:{doc.batch}")


def recipe_accept_signature_gate(doc: Any, method: str | None = None) -> None:
	"""`Recipe Governance.validate` — accepting a recipe authorises every later batch."""
	if doc.is_new():
		return
	target = doc.get("gov_state")
	if target != governance.ACCEPTED:
		return
	before = frappe.db.get_value(doc.doctype, doc.name, "gov_state")
	if before == target:
		return
	esignature.require(
		doc,
		esignature.ACT_RECIPE_ACCEPT,
		consumer=f"gov_state:{before}->{target}",
	)
