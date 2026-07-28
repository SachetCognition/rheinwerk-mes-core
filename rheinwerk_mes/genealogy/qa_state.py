"""Canonical batch `qa_state` machine (W2-2 · URS-W2-005, URS-W2-006).

The anchor `Batch` is never forked: `qa_state` is a Custom Field carried by the Frappe
workflow *Batch Quality Disposition* (`rheinwerk_mes.setup.w2_genealogy`), and every state
change — from the Desk workflow bar, from `transition()` or from any server-side caller —
funnels through `validate_qa_state_change()`, which

1. refuses illegal transitions (`LEGAL_TRANSITIONS`),
2. refuses a transition whose workflow row names a role the user does not hold,
3. runs the ordered gate callbacks registered under `rheinwerk_qa_state_gates`,
4. appends the `qa_state_history` audit row (state, user, timestamp, reason, trigger),
5. lets the registered post-transition effects run (blocking propagation, W2-3).

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-advanced-genealogy/src/main/java/com/qcadoo/mes/
advancedGenealogy/constants/BatchState.java:31-44` — Qcadoo knows `TRACKED` ⇄ `BLOCKED`,
reversible, with a reason on the state change. `Quarantined` is the deliberate Rheinwerk
addition recorded in URS-W2-006 (ADR-003); it is asserted as *new* behaviour, not parity.

Public surface for sibling W2 children — see `docs/design/W2-genealogy.md`:

* `transition(batch, target_state, reason=None, triggering_document=None)`
* `TransitionContext` — what a gate receives
* hooks key `rheinwerk_qa_state_gates` — ordered dotted paths of gate callables
  (the quality child wires the QI outcome through this hook, not by editing this module)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

QUARANTINED = "Quarantined"
RELEASED = "Released"
BLOCKED = "Blocked"

#: Every batch enters the estate quarantined (URS-W2-006 AC-1) unless its item is
#: QC-exempt (`qc_exempt` Custom Field on the anchor Item).
INITIAL_STATE = QUARANTINED

STATES: tuple[str, ...] = (QUARANTINED, RELEASED, BLOCKED)

#: Qcadoo `BatchState.java:31-44` gives the reversible TRACKED ⇄ BLOCKED pair; the
#: Quarantined entry state adds exactly two edges (release by inspection, block by QA).
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
	QUARANTINED: frozenset({RELEASED, BLOCKED}),
	RELEASED: frozenset({BLOCKED}),
	BLOCKED: frozenset({RELEASED}),
}

#: A disposition that takes stock out of use, or puts it back, must name its reason
#: (URS-W2-006 AC-3; Qcadoo carries the reason on the batch state change).
REASON_REQUIRED_STATES: frozenset[str] = frozenset({BLOCKED, RELEASED})

GATE_HOOK = "rheinwerk_qa_state_gates"

#: Frappe Workflow carrying `qa_state` on the anchor Batch.
WORKFLOW_NAME = "Batch Quality Disposition"

#: German pill labels (design skill — status pill = icon + label + colour).
STATE_LABELS: dict[str, str] = {
	QUARANTINED: "Quarantäne",
	RELEASED: "Freigegeben",
	BLOCKED: "Gesperrt",
}


def allowed_targets(state: str | None) -> frozenset[str]:
	"""Legal target states reachable from `state`."""
	return LEGAL_TRANSITIONS.get(state or INITIAL_STATE, frozenset())


def is_legal(from_state: str | None, to_state: str) -> bool:
	return to_state in allowed_targets(from_state)


@dataclass
class TransitionContext:
	"""Everything a `qa_state` gate callback needs to judge one transition."""

	doc: Any
	from_state: str
	to_state: str
	reason: str | None = None
	triggering_document: str | None = None
	errors: list[str] = field(default_factory=list)

	def refuse(self, message: str) -> None:
		self.errors.append(message)


def _gate_callables() -> list:
	return [frappe.get_attr(path) for path in frappe.get_hooks(GATE_HOOK) or []]


def run_gates(context: TransitionContext) -> None:
	"""Run every registered gate in hook order; refuse the transition if any objected."""
	for gate in _gate_callables():
		returned = gate(context)
		if isinstance(returned, Iterable) and not isinstance(returned, (str, bytes)):
			context.errors.extend(returned)
	if context.errors:
		frappe.throw(
			"<br>".join(context.errors),
			title=_("Verwendungsentscheid abgelehnt: {0} → {1}").format(
				_(STATE_LABELS[context.from_state]), _(STATE_LABELS[context.to_state])
			),
		)


# --------------------------------------------------------------------------------------
# Core gate owned by this module (URS-W2-006 AC-3). Registered first in hooks.py.
# --------------------------------------------------------------------------------------


def reason_gate(context: TransitionContext) -> None:
	"""Blocking and releasing require a reason (URS-W2-006 AC-3)."""
	if context.to_state in REASON_REQUIRED_STATES and not (context.reason or "").strip():
		context.refuse(
			_("Für den Zustand {0} ist eine Begründung erforderlich (Charge {1}).").format(
				_(STATE_LABELS[context.to_state]), context.doc.name
			)
		)


# --------------------------------------------------------------------------------------
# Transition entrypoint and document hooks
# --------------------------------------------------------------------------------------


def _load(batch: Any) -> Any:
	return frappe.get_doc("Batch", batch) if isinstance(batch, str) else batch


@frappe.whitelist()
def transition(
	batch: Any,
	target_state: str,
	reason: str | None = None,
	triggering_document: str | None = None,
) -> Any:
	"""Move a batch to `target_state` — the single `qa_state` transition entrypoint.

	`triggering_document` names the record that caused the change (e.g. the Quality
	Inspection that released the batch), and is recorded on the audit row.
	"""
	doc = _load(batch)
	doc.flags.qa_state_reason = reason
	doc.flags.qa_state_trigger = triggering_document
	doc.qa_state = target_state
	if doc.meta.has_field("qa_state_reason"):
		# Always overwritten — the reason of the *previous* disposition must never satisfy
		# the reason gate of this one (URS-W2-006 AC-3).
		doc.qa_state_reason = reason
	doc.save(ignore_permissions=False)
	return doc


def qc_exempt(item: str | None) -> bool:
	"""True when the item is exempt from the quarantine-by-default policy (URS-W2-006)."""
	if not item:
		return False
	if not frappe.get_meta("Item").get_field("qc_exempt"):
		return False
	return bool(frappe.db.get_value("Item", item, "qc_exempt"))


def set_default_qa_state(doc: Any, method: str | None = None) -> None:
	"""`Batch.before_insert` — every new batch starts Quarantined (URS-W2-006 AC-1)."""
	if not doc.meta.has_field("qa_state"):
		return
	if not doc.get("qa_state"):
		doc.qa_state = RELEASED if qc_exempt(doc.get("item")) else INITIAL_STATE


def validate_qa_state_change(doc: Any, method: str | None = None) -> None:
	"""`Batch.validate` — the one funnel every `qa_state` change passes through."""
	if not doc.meta.has_field("qa_state"):
		return
	if doc.get("__islocal") or not frappe.db.exists("Batch", doc.name):
		set_default_qa_state(doc)
		return

	from_state = frappe.db.get_value("Batch", doc.name, "qa_state") or INITIAL_STATE
	to_state = doc.get("qa_state") or INITIAL_STATE
	if to_state == from_state:
		return

	if to_state not in LEGAL_TRANSITIONS:
		frappe.throw(
			_("Unbekannter Qualitätszustand: {0}").format(to_state),
			title=_("Verwendungsentscheid abgelehnt"),
		)
	if not is_legal(from_state, to_state):
		frappe.throw(
			_("Übergang {0} → {1} ist für Charge {2} nicht zulässig. Zulässig sind: {3}.").format(
				_(STATE_LABELS[from_state]),
				_(STATE_LABELS[to_state]),
				doc.name,
				", ".join(_(STATE_LABELS[state]) for state in sorted(allowed_targets(from_state))),
			),
			title=_("Verwendungsentscheid abgelehnt"),
		)

	_assert_role_allowed(from_state, to_state)

	reason = doc.flags.get("qa_state_reason") or doc.get("qa_state_reason")
	context = TransitionContext(
		doc=doc,
		from_state=from_state,
		to_state=to_state,
		reason=reason,
		triggering_document=doc.flags.get("qa_state_trigger"),
	)
	run_gates(context)
	_append_history(doc, context)
	doc.flags.qa_state_transition = (from_state, to_state)


def _assert_role_allowed(from_state: str, to_state: str) -> None:
	"""Only the quality-inspector role may dispose of a batch (URS-W2-006 AC-4)."""
	roles = frappe.get_all(
		"Workflow Transition",
		filters={"parent": WORKFLOW_NAME, "state": from_state, "next_state": to_state},
		pluck="allowed",
	)
	if not roles:
		return
	if set(roles) & set(frappe.get_roles()):
		return
	frappe.throw(
		_("Der Übergang {0} → {1} ist der Rolle {2} vorbehalten.").format(
			_(STATE_LABELS[from_state]), _(STATE_LABELS[to_state]), ", ".join(sorted(roles))
		),
		frappe.PermissionError,
		title=_("Verwendungsentscheid abgelehnt"),
	)


def _append_history(doc: Any, context: TransitionContext) -> None:
	"""Write the audit row (URS-W2-006 AC-2/AC-3; Qcadoo batch state change)."""
	doc.append(
		"qa_state_history",
		{
			"from_state": context.from_state,
			"to_state": context.to_state,
			"changed_by": frappe.session.user,
			"changed_at": now_datetime(),
			"reason": context.reason or None,
			"triggering_document": context.triggering_document or None,
		},
	)


def state_history(batch: str) -> list[dict[str, Any]]:
	"""Audit rows of `batch`, oldest first — convenience reader for siblings/tests."""
	doc = frappe.get_doc("Batch", batch)
	return [
		{
			"from_state": row.from_state,
			"to_state": row.to_state,
			"changed_by": row.changed_by,
			"changed_at": row.changed_at,
			"reason": row.reason,
			"triggering_document": row.triggering_document,
		}
		for row in doc.get("qa_state_history") or []
	]


def current_state(batch: str) -> str:
	"""`qa_state` of `batch`, defaulting to the entry state for pre-W2 records."""
	return frappe.db.get_value("Batch", batch, "qa_state") or INITIAL_STATE
