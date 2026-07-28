"""The hazmat dispatch gate at the shipping boundary (W3-6 · URS-W3-018 AC-2).

One rule, in one place: **a hazmat batch may not leave the estate while its ADR transport
data is incomplete.** "Leaving the estate" is the outward finished-goods posting — a
submitted outward `Stock Entry` (Material Issue, Send to Subcontractor) or a `Delivery Note`
— so the gate hangs off those anchor documents exactly the way the W1 expiry hard stop does
(`rheinwerk_mes.execution_gating.expiry`, registered as a `doc_events` validate hook in
`hooks.py`): no anchor DocType is forked, no substrate rule is weakened, and the refusal is
written to the same immutable `Execution Gate Log` as every other gated action
(URS-W1-033 / URS-W3-021) through `execution_gating.audit.log_refusal`.

Why not the `rheinwerk_exec_state_gates` registry: that registry gates *production-order
state transitions* (`manufacturing_core.exec_state.transition`), and a dispatch is a stock
posting, not an order transition — the same reason W1-3's expiry stop is a document hook.
`execution_gating/**` is therefore consumed, never edited (programme rule 3).

The refusal names **rule, record and resolution** German-first and is modal-grade
(`frappe.throw` → the Desk renders a modal, the Terminal its blocking gate card), never a
toast (design skill § "Hard gates look hard").

Scanner path: `resolve_dispatch_scan` reuses the existing W1 resolver
(`manufacturing_core.shopfloor.scanner.resolve`) and adds the W2-8 handling unit as a leg —
scanning `HU-000123` resolves the unit and the batch standing on it (URS-W3-018 design
conformance, URS-W3-020 AC-2).
"""

from __future__ import annotations

import time
from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.execution_gating import audit
from rheinwerk_mes.regulatory_hazmat import contracts, labels, profiles

GATE = "hazmat_dispatch_gate"

#: Stock Entry purposes that hand material over to a third party — the dispatch boundary.
#: Internal transfers and consumption are *not* dispatch: they stay inside the estate and are
#: governed by the W1/W2 gates (expiry, blocked batch, quarantine exit).
DISPATCH_PURPOSES: frozenset[str] = frozenset({"Material Issue", "Send to Subcontractor"})

HANDLING_UNIT = "Handling Unit"


# --------------------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------------------


def adr_verdict(batch: str) -> tuple[str | None, tuple[str, ...]]:
	"""ADR verdict of one batch: `(profile name, missing ADR fields)`.

	Non-hazardous stock — no effective hazmat profile — is never gated: `(None, ())`.
	"""
	profile = profiles.effective_profile(batch=batch)
	if not profile:
		return None, ()
	return profile.get("name"), contracts.missing_adr_fields(profile)


def dispatch_blockers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Every dispatched row whose hazmat profile still owes ADR data (URS-W3-018 AC-2)."""
	blockers: list[dict[str, Any]] = []
	seen: set[tuple[str, str]] = set()
	for row in rows:
		batch = row.get("batch")
		if not batch:
			continue
		profile, missing = adr_verdict(batch)
		if not missing:
			continue
		key = (batch, profile or "")
		if key in seen:
			continue
		seen.add(key)
		blockers.append(
			{
				"batch": batch,
				"item": row.get("item"),
				"profile": profile,
				"missing": list(missing),
				"missing_labels": [_(contracts.ADR_FIELD_LABELS[field]) for field in missing],
			}
		)
	return blockers


def enforce_adr_completeness(doc: Any, method: str | None = None) -> None:
	"""`validate` hook on the outward anchor documents — refuse incomplete ADR data.

	URS-W3-018 AC-2 · TC-W3-022. Registered additively in `hooks.py` for `Stock Entry`
	(dispatch purposes only) and `Delivery Note`.
	"""
	rows = _dispatched_rows(doc)
	if not rows:
		return
	blockers = dispatch_blockers(rows)
	if not blockers:
		return

	rule = _(
		"Gefahrgut darf nur mit vollständigen ADR-Transportdaten versandt werden "
		"(UN-Nummer, offizielle Benennung, ADR-Klasse, Verpackungsgruppe)."
	)
	record = "<br>".join(
		_("Artikel {0}, Charge {1} — Profil {2}, fehlende Angaben: {3}").format(
			blocker["item"],
			blocker["batch"],
			blocker["profile"] or _("nicht hinterlegt"),
			", ".join(blocker["missing_labels"]),
		)
		for blocker in blockers
	)
	resolution = _(
		"Gefahrstoffprofil vervollständigen (Technologe, Feld „ADR-Transportdaten“) "
		"und den Versand erneut buchen."
	)
	for blocker in blockers:
		audit.log_refusal(
			gate=GATE,
			rule=rule,
			document=frappe._dict(doctype="Batch", name=blocker["batch"]),
			detail=_("Versand {0} abgelehnt: Charge {1}, fehlende ADR-Angaben: {2}.").format(
				doc.get("name") or _("(Entwurf)"),
				blocker["batch"],
				", ".join(blocker["missing_labels"]),
			),
		)
	frappe.throw(
		"<br>".join(
			[
				_("<b>Regel:</b> {0}").format(rule),
				_("<b>Datensatz:</b> {0}").format(record),
				_("<b>Behebung:</b> {0}").format(resolution),
			]
		),
		title=_("Versand abgelehnt: ADR-Daten unvollständig"),
	)


def _dispatched_rows(doc: Any) -> list[dict[str, Any]]:
	"""The rows of an outward anchor document that actually dispatch stock."""
	if doc.doctype == "Stock Entry":
		if (doc.get("purpose") or "") not in DISPATCH_PURPOSES:
			return []
		rows = [row for row in doc.get("items") or [] if row.get("s_warehouse")]
	elif doc.doctype == "Delivery Note":
		rows = list(doc.get("items") or [])
	else:
		return []
	dispatched: list[dict[str, Any]] = []
	for row in rows:
		for batch in _row_batches(row):
			dispatched.append({"item": row.get("item_code"), "batch": batch})
	return dispatched


def _row_batches(row: Any) -> list[str]:
	"""Batches one row draws from — the legacy `batch_no` field or its bundle.

	Mirrors `execution_gating.expiry._row_batches`, whose helper is module-private; see the
	PR note asking for it to be published so the two gates share one reader.
	"""
	if row.get("batch_no"):
		return [row.batch_no]
	bundle = row.get("serial_and_batch_bundle")
	if not bundle:
		return []
	batches = frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, pluck="batch_no")
	return [batch for batch in batches if batch]


# --------------------------------------------------------------------------------------
# Dispatch station: scanner path and label preview
# --------------------------------------------------------------------------------------


def handling_unit_batches(handling_unit: str) -> list[dict[str, Any]]:
	"""Batch contents of a W2-8 handling unit, largest quantity first."""
	rows = frappe.get_all(
		"Handling Unit Content",
		filters={"parent": handling_unit, "parenttype": HANDLING_UNIT},
		fields=["item", "batch_no", "qty", "uom"],
		order_by="qty desc",
	)
	return [dict(row) for row in rows if row.get("batch_no")]


def resolve_dispatch_scan(code: str) -> dict[str, Any]:
	"""Resolve a scan at the dispatch station: handling unit *or* batch.

	The W1 resolver (`manufacturing_core.shopfloor.scanner.resolve`) already resolves
	orders, job cards, batches and items and is reused unchanged; the handling unit is the
	one leg it does not know, so it is resolved here first — a barcode like `HU-000123` is a
	unit, everything else falls through to the shared resolver.
	"""
	from rheinwerk_mes.manufacturing_core.shopfloor import scanner

	scanned = (code or "").strip()
	unit = _handling_unit_name(scanned)
	if unit:
		contents = handling_unit_batches(unit)
		batch = contents[0]["batch_no"] if contents else None
		return {
			"recognised": True,
			"kind": "handling_unit",
			"doctype": HANDLING_UNIT,
			"name": unit,
			"highlight": f"handling_unit:{unit}",
			"confirm_sound": "scan-ok",
			"label": _("Ladeeinheit {0}").format(scanned),
			"batch": batch,
			"contents": contents,
			"warehouse": frappe.db.get_value(HANDLING_UNIT, unit, "warehouse"),
		}
	resolved = scanner.resolve(scanned)
	if resolved.get("kind") == scanner.BATCH:
		resolved["batch"] = resolved["name"]
	return resolved


def _handling_unit_name(code: str) -> str | None:
	"""A scanned code that is a handling unit — by barcode or by document name."""
	if not code or not frappe.db.exists("DocType", HANDLING_UNIT):
		return None
	by_barcode = frappe.db.get_value(HANDLING_UNIT, {"barcode": code}, "name")
	if by_barcode:
		return by_barcode
	return frappe.db.get_value(HANDLING_UNIT, code, "name") if frappe.db.exists(HANDLING_UNIT, code) else None


@frappe.whitelist()
def scan_for_dispatch(code: str) -> dict[str, Any]:
	"""Whitelisted dispatch-station scan: resolution **plus** the label of what was scanned.

	One round trip, because the clerk's next action is reading the label; `server_ms` is the
	measurement URS-W3-020 AC-2 budgets (≤ 300 ms server-confirmed).
	"""
	started = time.perf_counter()
	resolved = resolve_dispatch_scan(code)
	batch = resolved.get("batch")
	if batch:
		resolved["label_data"] = labels.label_model(
			batch,
			warehouse=resolved.get("warehouse"),
			handling_unit=resolved["name"] if resolved.get("kind") == "handling_unit" else None,
		)
	resolved["server_ms"] = round((time.perf_counter() - started) * 1000, 3)
	return resolved
