"""Expired-batch consumption hard stop (W1-3 · URS-W1-013, policy URS-W1-030).

The estate-wide policy is the **hard stop**: an outward posting or a pick against a batch
past its `expiry_date` is refused (a deliberate deviation from Plant A's FEFO-advisory
Qcadoo behaviour, recorded in URS-W1-030).

The substrate enforces this for pick lists
(`erpnext/stock/doctype/pick_list/pick_list.py:286-311`, `validate_expired_batches`, on
save) — W1-3 only verifies that rule still fires through our workflow. It does **not**
enforce it for stock *consumption*: `stock_ledger_entry.py:287-299` (`validate_batch`)
skips its expiry throw whenever `voucher_type == "Stock Entry"`, and
`stock/services/serial_batch_bundle_service.py:110-112` skips
`validate_serialized_batch`'s `BatchExpiredError` for the purposes *Material Issue* and
*Material Transfer*. On this substrate version a Material Issue from an expired batch
therefore posts silently (verified on the dev site before the gate was added).

Closing that gap is what this module does — as a `rheinwerk_mes` hook on the anchor
`Stock Entry` (no anchor DocType is forked and no substrate rule is weakened): every
outward row is checked against its batch's expiry on save, and the refusal is a hard-gate
modal naming the rule, the batch with its expiry in DD.MM.YYYY and the resolution
(URS-W1-013 design conformance), logged immutably like every other gated action
(URS-W1-033).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, nowdate

from rheinwerk_mes.execution_gating import audit

GATE = "expiry_gate"

#: Stock Entry purposes whose source rows draw stock and therefore consume a batch.
OUTWARD_PURPOSES: frozenset[str] = frozenset(
	{
		"Material Issue",
		"Material Transfer",
		"Material Transfer for Manufacture",
		"Manufacture",
		"Repack",
		"Send to Subcontractor",
	}
)


def enforce_batch_expiry(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.validate` — refuse outward rows consuming an expired batch (URS-W1-013).

	Rows without a source warehouse (pure receipts) are ignored: the policy refuses
	*consumption*, not intake, and a batch may legitimately be received before it expires.
	"""
	if doc.get("purpose") and doc.purpose not in OUTWARD_PURPOSES:
		return
	posting_date = getdate(doc.get("posting_date") or nowdate())
	expired: list[tuple[str, Any, str]] = []
	for row in doc.get("items") or []:
		if not row.get("s_warehouse"):
			continue
		for batch_no in _row_batches(row):
			expiry = frappe.db.get_value("Batch", batch_no, "expiry_date")
			if expiry and getdate(expiry) < posting_date:
				expired.append((batch_no, expiry, row.item_code))
	if not expired:
		return

	rule = _("Chargen nach Ablauf des Verfallsdatums dürfen nicht verbraucht werden (Sperrregel).")
	record = "<br>".join(
		_("Charge {0} (Artikel {1}), Verfallsdatum {2}").format(
			batch_no, item_code, formatdate(expiry, "dd.MM.yyyy")
		)
		for batch_no, expiry, item_code in expired
	)
	resolution = _(
		"Nicht verfallenen Bestand auswählen oder eine QA-Verwendungsentscheidung für die Charge einholen."
	)
	for batch_no, expiry, _item_code in expired:
		audit.log_refusal(
			gate=GATE,
			rule=rule,
			document=frappe._dict(doctype="Batch", name=batch_no),
			detail=_("Buchung {0} vom {1} abgelehnt: Charge {2} verfallen am {3}.").format(
				doc.get("name") or _("(Entwurf)"),
				formatdate(posting_date, "dd.MM.yyyy"),
				batch_no,
				formatdate(expiry, "dd.MM.yyyy"),
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
		title=_("Verbrauch abgelehnt: verfallene Charge"),
	)


def _row_batches(row: Any) -> list[str]:
	"""Batches a Stock Entry row draws from — legacy `batch_no` field or its bundle."""
	if row.get("batch_no"):
		return [row.batch_no]
	bundle = row.get("serial_and_batch_bundle")
	if not bundle:
		return []
	batches = frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, pluck="batch_no")
	return [batch for batch in batches if batch]
