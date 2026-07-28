"""Blocking: propagation, picking exclusion and the consumption stop (W2-3 · URS-W2-009…011).

Three behaviours hang off one `qa_state` (`qa_state.py`):

1. **Propagation** (URS-W2-009) — blocking a batch writes a *blocked-ancestor advisory* on
   every batch downstream of it in the forward genealogy, in the same transaction;
   unblocking removes exactly the advisories that named it, so a batch with another
   blocked ancestor keeps its advisory. Downstream batches are never auto-blocked: their
   own `qa_state` is untouched (the signed-off advisory semantics of URS-W2-009).
2. **Picking exclusion** (URS-W2-010) — `is_pickable()` is the single predicate the
   warehouse code consults; Blocked *and* Quarantined stock is excluded from picking
   proposals, allocation and reservable availability.
3. **Consumption stop** (URS-W2-011) — the anchor `Stock Entry` validate hook refuses any
   outward row drawing a Blocked batch, so the server is authoritative and the terminal
   cannot post around the UI gate.

Legacy baselines (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`advancedGenealogy/constants/BatchState.java:31-44` (BLOCKED batches are unusable until
tracked again) and `materialFlowResources/criteriaModifiers/ResourceCriteriaModifiers.java:59,70`
(resources of QC-blocked batches are filtered out of the resource lookups). Propagation
and the exclusion of *Quarantined* stock are the deliberate Rheinwerk deviations recorded
in URS-W2-009 / URS-W2-006.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.genealogy import links, qa_state, trace

ADVISORY_FIELD = "blocked_ancestors"

#: Rule identifiers named in every refusal and audit row, so the UI gate and the server
#: hook refuse with the *same* identifier (URS-W2-011 AC-2).
RULE_BLOCKED_CONSUMPTION = "blocked_batch_consumption"
RULE_BLOCKED_PICKING = "blocked_batch_exclusion"

#: States whose stock may not be picked, reserved or consumed (URS-W2-010).
NON_PICKABLE_STATES: frozenset[str] = frozenset({qa_state.BLOCKED, qa_state.QUARANTINED})


# --------------------------------------------------------------------------------------
# Exclusion predicate — the one place picking exclusion is decided
# --------------------------------------------------------------------------------------


def is_pickable(batch: str | None) -> bool:
	"""True when stock of `batch` may be proposed, reserved or issued (URS-W2-010).

	Batches unknown to the canonical model (non-batch rows) are pickable — the predicate
	only ever *removes* stock that carries a disposition forbidding use.
	"""
	if not batch:
		return True
	state = frappe.db.get_value("Batch", batch, "qa_state")
	if state is None:
		return True
	return state not in NON_PICKABLE_STATES


def pickable_batches(batches: Iterable[str]) -> list[str]:
	"""Filter helper for candidate lists (`ResourceCriteriaModifiers.java:59,70`)."""
	return [batch for batch in batches if is_pickable(batch)]


def excluded_qty(item: str, warehouse: str) -> Decimal:
	"""On-hand quantity of `item` in `warehouse` that is not available (URS-W2-010 AC-2).

	Subtracted from availability so a Quarantined or Blocked lot is neither reservable nor
	counted as available, while the physical on-hand figure stays untouched.
	"""
	from rheinwerk_mes.warehouse.availability import ledger_balance

	total = Decimal("0")
	rows = frappe.get_all(
		"Batch",
		filters={"item": item, "qa_state": ("in", sorted(NON_PICKABLE_STATES))},
		pluck="name",
	)
	for batch in rows:
		balance = ledger_balance(item, warehouse, batch, consider_expired=True)
		if balance > 0:
			total += balance
	return total


def refusal_message(batch: str, *, rule: str, record_detail: str) -> str:
	"""Hard-gate modal body naming rule, record and resolution (design skill)."""
	rules = {
		RULE_BLOCKED_CONSUMPTION: _(
			"Gesperrte Chargen dürfen nicht in Fertigungsaufträge verbraucht werden (Sperrregel)."
		),
		RULE_BLOCKED_PICKING: _(
			"Bestand gesperrter oder in Quarantäne befindlicher Chargen ist von der Entnahme ausgeschlossen."
		),
	}
	return "<br>".join(
		[
			_("<b>Regel:</b> {0} [{1}]").format(rules[rule], rule),
			_("<b>Datensatz:</b> {0}").format(record_detail),
			_("<b>Behebung:</b> QA-Freigabe der Charge {0} erforderlich.").format(batch),
		]
	)


def assert_pickable(batch: str, handling_unit: str | None = None) -> None:
	"""Refuse a scan/pick of non-pickable stock with a logged modal (URS-W2-010 AC-3)."""
	if is_pickable(batch):
		return
	state = qa_state.current_state(batch)
	record = _("Charge {0} ({1})").format(batch, _(qa_state.STATE_LABELS[state]))
	if handling_unit:
		record = _("{0}, Ladeeinheit {1}").format(record, handling_unit)
	message = refusal_message(batch, rule=RULE_BLOCKED_PICKING, record_detail=record)
	audit.log_refusal(
		gate=RULE_BLOCKED_PICKING,
		rule=RULE_BLOCKED_PICKING,
		document=frappe._dict(doctype="Batch", name=batch),
		from_state=state,
		detail=record,
	)
	frappe.throw(message, title=_("Entnahme abgelehnt: gesperrte Charge"))


# --------------------------------------------------------------------------------------
# Propagation (URS-W2-009)
# --------------------------------------------------------------------------------------


def _advisory_rows(batch: str) -> list[Any]:
	return frappe.get_all(
		"Blocked Ancestor Advisory",
		filters={"parent": batch, "parenttype": "Batch"},
		fields=["name", "ancestor_batch"],
	)


def propagate_block(batch: str, reason: str | None = None) -> list[str]:
	"""Write the blocked-ancestor advisory on every downstream batch (AC-1)."""
	flagged: list[str] = []
	for downstream in trace.descendants(batch):
		existing = {row.ancestor_batch for row in _advisory_rows(downstream)}
		if batch in existing:
			continue
		doc = frappe.get_doc("Batch", downstream)
		if not doc.meta.has_field(ADVISORY_FIELD):
			continue
		doc.append(
			ADVISORY_FIELD,
			{
				"ancestor_batch": batch,
				"reason": reason,
				"flagged_at": now_datetime(),
			},
		)
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		flagged.append(downstream)
	return flagged


def clear_block(batch: str) -> list[str]:
	"""Remove the advisories naming `batch`; other blocked ancestors keep theirs (AC-2)."""
	cleared: list[str] = []
	for downstream in trace.descendants(batch):
		rows = [row for row in _advisory_rows(downstream) if row.ancestor_batch == batch]
		if not rows:
			continue
		doc = frappe.get_doc("Batch", downstream)
		doc.set(
			ADVISORY_FIELD,
			[row for row in doc.get(ADVISORY_FIELD) or [] if row.ancestor_batch != batch],
		)
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		cleared.append(downstream)
	return cleared


def advisory_pill(batch: str) -> dict[str, Any] | None:
	"""Amber advisory pill (icon + label + colour) for a batch chip (AC-3)."""
	ancestors = trace.blocked_ancestors(batch)
	if not ancestors:
		return None
	return {
		"tone": "amber",
		"icon": "alert-triangle",
		"label": _("Gesperrter Vorgänger: {0}").format(", ".join(ancestors)),
		"ancestors": ancestors,
	}


def on_batch_update(doc: Any, method: str | None = None) -> None:
	"""`Batch.on_update` — run the propagation of the transition just validated."""
	transition = doc.flags.get("qa_state_transition")
	if not transition:
		return
	doc.flags.qa_state_transition = None
	_from_state, to_state = transition
	if to_state == qa_state.BLOCKED:
		propagate_block(doc.name, doc.get("qa_state_reason"))
	elif _from_state == qa_state.BLOCKED:
		clear_block(doc.name)


# --------------------------------------------------------------------------------------
# Consumption stop (URS-W2-011)
# --------------------------------------------------------------------------------------


def enforce_blocked_batch_consumption(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.validate` — refuse any outward row drawing a Blocked batch (AC-1/AC-2)."""
	blocked: list[tuple[str, str]] = []
	for row in doc.get("items") or []:
		if not row.get("s_warehouse"):
			continue
		for batch in links.row_batches(row):
			if qa_state.current_state(batch) == qa_state.BLOCKED:
				blocked.append((batch, row.item_code))
	if not blocked:
		return

	record = "<br>".join(
		_("Charge {0} (Artikel {1}), Auftrag {2}").format(batch, item, doc.get("work_order") or "—")
		for batch, item in blocked
	)
	for batch, _item in blocked:
		audit.log_refusal(
			gate=RULE_BLOCKED_CONSUMPTION,
			rule=RULE_BLOCKED_CONSUMPTION,
			document=frappe._dict(doctype="Batch", name=batch),
			from_state=qa_state.BLOCKED,
			detail=_("Buchung {0} abgelehnt: Charge {1} ist gesperrt.").format(
				doc.get("name") or _("(Entwurf)"), batch
			),
		)
	frappe.throw(
		refusal_message(blocked[0][0], rule=RULE_BLOCKED_CONSUMPTION, record_detail=record),
		title=_("Verbrauch abgelehnt: gesperrte Charge"),
	)
