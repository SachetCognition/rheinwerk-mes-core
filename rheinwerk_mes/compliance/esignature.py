"""Electronic signatures on dispositive acts — enforcement of DEC-W2-029 (URS-W2-029 AC-2).

W2 shipped the *decision*; this module is the enforcement the decision scheduled into W3.

Four acts require a signature, all of them declaring material or a recipe fit to the outside
world: releasing a batch, blocking a batch (incl. the block reversal), issuing a certificate
of analysis and accepting a recipe. Everything operational stays on its existing audit trail.

Signing and acting are two steps on purpose, so no existing public signature changes:

```python
esignature.sign(document_type="Batch", document_name="BATCH-A-0001",
                act=esignature.ACT_QA_RELEASE, password=…, reason=…)
qa_state.transition("BATCH-A-0001", "Released", reason=…)   # the gate spends the signature
```

The signature is a short-lived, single-use token: it names the signer, the act, the exact
document and the hash of the signed payload, expires after `FRESHNESS_SECONDS`, and is
stamped consumed by the gate that spends it, so it can never be replayed on a second act.

Enforcement is an estate switch (`Rheinwerk Compliance Settings.esignature_enforced`),
shipped **off** and flipped at cutover: every automated release path (an accepted inspection
releasing its own batch, the migration loaders, fixture seeding) has to carry a signer first,
which is W4 work. Signing, its audit trail and the signature report work regardless of the
switch — see `docs/design/W3-esignature-enforcement.md` §4.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime
from frappe.utils.password import check_password

from rheinwerk_mes.execution_gating import audit

DOCTYPE = "Electronic Signature"

#: A signature is valid for this long and for exactly one act (design decision D2 in
#: `docs/design/W3-esignature-enforcement.md`).
FRESHNESS_SECONDS = 300

ACT_QA_RELEASE = "qa_state:Released"
ACT_QA_BLOCK = "qa_state:Blocked"
ACT_COA_ISSUE = "coa:issue"
ACT_RECIPE_ACCEPT = "gov_state:Accepted"

#: Fixed German-first vocabulary — what the signer declares (DEC-W2-029).
MEANINGS: dict[str, str] = {
	ACT_QA_RELEASE: "Freigegeben",
	ACT_QA_BLOCK: "Gesperrt",
	ACT_COA_ISSUE: "Zertifiziert",
	ACT_RECIPE_ACCEPT: "Rezeptur genehmigt",
}

#: Acts whose signature must carry a reason (blocking and its reversal — DEC-W2-029).
REASON_REQUIRED_ACTS: frozenset[str] = frozenset({ACT_QA_BLOCK, ACT_QA_RELEASE})

ACT_LABELS: dict[str, str] = {
	ACT_QA_RELEASE: "Chargenfreigabe",
	ACT_QA_BLOCK: "Chargensperre",
	ACT_COA_ISSUE: "Ausstellung eines Analysenzertifikats",
	ACT_RECIPE_ACCEPT: "Rezeptfreigabe",
}

SIGNATURE_GATE = "electronic_signature"
SIGNATURE_RULE = "URS-W2-029"

SETTINGS_DOCTYPE = "Rheinwerk Compliance Settings"


def enforced() -> bool:
	"""True when a missing signature refuses the act (estate switch, off until cutover)."""
	return bool(frappe.db.get_single_value(SETTINGS_DOCTYPE, "esignature_enforced"))


def payload_hash(payload: dict[str, Any]) -> str:
	"""Hash of the signed field set, so a later edit of the signed record is detectable."""
	canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
	return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@frappe.whitelist()
def sign(
	document_type: str,
	document_name: str,
	act: str,
	password: str,
	reason: str | None = None,
	transition: str | None = None,
) -> str:
	"""Re-authenticate the current user and record their signature for one act.

	Returns the signature name. `password` is verified against the *session user's* own
	credential and never stored; a delegated or stored credential cannot produce a
	signature because there is no parameter to pass one.
	"""
	if act not in MEANINGS:
		frappe.throw(_("Unbekannte unterschriftspflichtige Handlung: {0}").format(act))
	if act in REASON_REQUIRED_ACTS and not (reason or "").strip():
		frappe.throw(
			_("Für {0} ist eine Begründung erforderlich.").format(_(ACT_LABELS[act])),
			title=_("Unterschrift unvollständig"),
		)
	user = frappe.session.user
	try:
		check_password(user, password)
	except frappe.AuthenticationError:
		frappe.throw(
			_("Kennwort nicht korrekt — die Unterschrift wurde nicht erteilt."),
			frappe.AuthenticationError,
			title=_("Unterschrift abgelehnt"),
		)

	document = frappe.get_doc(document_type, document_name)
	signature = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"signer": user,
			"signer_full_name": frappe.db.get_value("User", user, "full_name"),
			"meaning": MEANINGS[act],
			"signed_at": now_datetime(),
			"document_type": document_type,
			"document_name": document_name,
			"act": act,
			"transition": transition,
			"reason": reason,
			"payload_hash": payload_hash(signed_payload(document, act)),
		}
	).insert(ignore_permissions=True)
	audit.log_transition(
		gate=SIGNATURE_GATE,
		rule=SIGNATURE_RULE,
		document=document,
		from_state=None,
		to_state=signature.meaning,
		detail=_("{0} elektronisch unterzeichnet durch {1} ({2}).").format(
			_(ACT_LABELS[act]), signature.signer_full_name or user, signature.name
		),
	)
	return signature.name


def signed_payload(document: Any, act: str) -> dict[str, Any]:
	"""The field set a signature covers — small, act-specific, and stable across reloads."""
	if act in (ACT_QA_RELEASE, ACT_QA_BLOCK):
		return {
			"batch": document.name,
			"item": document.get("item"),
			"expiry_date": document.get("expiry_date"),
		}
	if act == ACT_COA_ISSUE:
		# Signed against the inspection whose readings the certificate publishes.
		return {
			"quality_inspection": document.name,
			"batch": document.get("batch_no"),
			"status": document.get("status"),
		}
	return {
		"recipe": document.get("bom") or document.name,
		"routing": document.get("routing"),
		"version": document.get("version"),
	}


def pending(document_type: str, document_name: str, act: str) -> str | None:
	"""The signer's newest unspent, unexpired signature for this exact act, if any."""
	names = frappe.get_all(
		DOCTYPE,
		filters={
			"document_type": document_type,
			"document_name": document_name,
			"act": act,
			"signer": frappe.session.user,
			"consumed_by": ("is", "not set"),
			"signed_at": (">=", add_to_date(now_datetime(), seconds=-FRESHNESS_SECONDS)),
		},
		order_by="signed_at desc",
		limit=1,
		pluck="name",
	)
	return names[0] or None if names else None


def require(
	document: Any,
	act: str,
	consumer: str,
	*,
	alternatives: Sequence[tuple[str, str]] = (),
) -> str | None:
	"""Spend the signature required for `act` on `document`, or refuse the act.

	`consumer` names what the signature is spent on (the transition or the issuing call) and
	is stamped on the signature, so a replay on a second act is impossible. `alternatives`
	are further `(document_type, document_name)` pairs a valid signature may name — an
	inspection that releases its own batch is signed as the inspection: one act, one
	signature.

	Returns the spent signature, or `None` when enforcement is off and none was given.
	"""
	name = pending(document.doctype, document.name, act)
	for alternative_type, alternative_name in alternatives:
		if name:
			break
		name = pending(alternative_type, alternative_name, act)
	if not name and not enforced():
		return None
	if not name:
		frappe.throw(
			_(
				"{0} erfordert eine elektronische Unterschrift. Regel: {1} (DEC-W2-029). "
				"Datensatz: {2}. Lösung: Handlung mit Kennwortbestätigung unterzeichnen "
				"(gültig {3} Minuten)."
			).format(
				_(ACT_LABELS[act]),
				SIGNATURE_RULE,
				document.name,
				FRESHNESS_SECONDS // 60,
			),
			title=_("Unterschrift erforderlich"),
		)
	signature = frappe.get_doc(DOCTYPE, name)
	signed_document = (
		document
		if signature.document_name == document.name
		else frappe.get_doc(signature.document_type, signature.document_name)
	)
	if signature.payload_hash != payload_hash(signed_payload(signed_document, act)):
		frappe.throw(
			_(
				"Der unterzeichnete Datensatz {0} hat sich nach der Unterschrift geändert. "
				"Bitte erneut unterzeichnen."
			).format(signature.document_name),
			title=_("Unterschrift ungültig"),
		)
	signature.db_set(
		{"consumed_by": consumer, "consumed_at": now_datetime()},
		update_modified=False,
	)
	return signature.name


@frappe.whitelist()
def batch_report(batch: str) -> list[dict[str, Any]]:
	"""Every signature bearing on one batch — the audit report DEC-W2-029 asks for.

	A batch is signed directly (release, block), through the inspection that dispositioned
	it, and through the certificates issued from that inspection; all three are collected
	here so an auditor reads one list per batch, oldest signature first.
	"""
	if not frappe.has_permission("Batch", "read", doc=batch):
		frappe.throw(
			_("Keine Leseberechtigung für Charge {0}.").format(batch),
			frappe.PermissionError,
		)
	rows = signatures_for("Batch", batch)
	for inspection in frappe.get_all("Quality Inspection", filters={"batch_no": batch}, pluck="name"):
		rows.extend(signatures_for("Quality Inspection", inspection))
	for certificate in frappe.get_all("CoA Certificate", filters={"batch": batch}, pluck="name"):
		rows.extend(signatures_for("CoA Certificate", certificate))
	return sorted(rows, key=lambda row: row["signed_at"])


def signatures_for(document_type: str, document_name: str) -> list[dict[str, Any]]:
	"""Signature report of one record (batch or certificate) — oldest first."""
	return frappe.get_all(
		DOCTYPE,
		filters={"document_type": document_type, "document_name": document_name},
		fields=[
			"name",
			"signer",
			"signer_full_name",
			"meaning",
			"act",
			"transition",
			"reason",
			"signed_at",
			"consumed_by",
		],
		order_by="signed_at asc",
	)
