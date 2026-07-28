"""Certificates of Analysis (W2-5 · URS-W2-017…019).

White space in all three legacy systems (dossier §6.3): there is no parity contract to
satisfy, so the behaviour is designed from the URS — the decisions (numbering, PDF path,
immutability/versioning, retention, German-first content) are recorded in
`docs/design/W2-quality-coa.md`.

Surface:

```python
coa.issue(batch)                       # URS-W2-017 — new certificate, PDF attached
coa.certificates_for_batch(batch)      # URS-W2-019 — retrieval, newest version first
coa.view_model(certificate)            # URS-W2-018 — CoA + embedded Trace Ribbon
coa.search(term)                       # URS-W2-019 — Command-Dashboard drill-down
coa.render_html(certificate)           # the print/PDF body
```
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, formatdate, get_url_to_form, today

from rheinwerk_mes.genealogy import qa_state, ribbon
from rheinwerk_mes.quality import inspections
from rheinwerk_mes.quality.doctype.coa_certificate.coa_certificate import ISSUED, SUPERSEDED

DOCTYPE = "CoA Certificate"

#: Jinja body of the certificate — also the PDF source (design decision D3).
TEMPLATE = "rheinwerk_mes/quality/templates/coa_certificate.html"

STATUS_LABELS: dict[str, str] = {
	ISSUED: "Ausgestellt",
	SUPERSEDED: "Ersetzt",
}


def _german_date(value: Any) -> str:
	"""DD.MM.YYYY — the estate's only date rendering (design skill)."""
	return formatdate(value, "dd.MM.yyyy") if value else ""


def kg(value: Any) -> str:
	text = f"{flt(value):.3f}".rstrip("0").rstrip(".") or "0"
	return f"{text.replace('.', ',')} kg"


# --------------------------------------------------------------------------------------
# Issue (URS-W2-017)
# --------------------------------------------------------------------------------------


def _refuse_without_inspection(batch: str) -> str:
	"""The CoA needs an Accepted inspection; refuse naming what is missing (AC-2)."""
	accepted = inspections.accepted_inspection(batch)
	if accepted:
		return accepted
	rejected = inspections.rejected_inspections(batch)
	if rejected:
		frappe.throw(
			_(
				"Die Prüfung {0} der Charge {1} ist abgelehnt — es kann kein Analysenzertifikat ausgestellt werden."
			).format(rejected[0]["name"], batch),
			title=_("Analysenzertifikat abgelehnt"),
		)
	frappe.throw(
		_("Für die Charge {0} liegt keine angenommene Qualitätsprüfung vor.").format(batch),
		title=_("Analysenzertifikat abgelehnt"),
	)
	return ""


def latest_certificate(batch: str) -> str | None:
	rows = certificates_for_batch(batch)
	return rows[0]["name"] if rows else None


@frappe.whitelist()
def issue(batch: str, inspection: str | None = None, attach_pdf: bool = True) -> Any:
	"""Issue a CoA for `batch` from its Accepted inspection (URS-W2-017 AC-1)."""
	inspection = inspection or _refuse_without_inspection(batch)
	batch_doc = frappe.get_doc("Batch", batch)
	qi = frappe.get_doc("Quality Inspection", inspection)
	if qi.status != inspections.ACCEPTED or qi.docstatus != 1:
		frappe.throw(
			_("Die Prüfung {0} ist nicht angenommen und gebucht.").format(inspection),
			title=_("Analysenzertifikat abgelehnt"),
		)

	previous = latest_certificate(batch)
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"batch": batch,
			"item": batch_doc.item,
			"item_name": frappe.db.get_value("Item", batch_doc.item, "item_name"),
			"certificate_status": ISSUED,
			"version": (frappe.db.get_value(DOCTYPE, previous, "version") or 0) + 1 if previous else 1,
			"supersedes": previous,
			"quality_inspection": qi.name,
			"inspection_template": qi.quality_inspection_template,
			"inspection_date": qi.report_date,
			"issue_date": today(),
			"signatory": frappe.session.user,
			"signatory_name": frappe.db.get_value("User", frappe.session.user, "full_name"),
			"manufacturing_date": batch_doc.get("manufacturing_date"),
			"expiry_date": batch_doc.get("expiry_date"),
			# The canonical original quantity, falling back to the anchor's batch quantity
			# for batches created before the W2 canonical fields were backfilled.
			"qty_original": flt(batch_doc.get("qty_original")) or flt(batch_doc.get("batch_qty")),
			"stock_uom": frappe.db.get_value("Item", batch_doc.item, "stock_uom"),
			"readings": [
				{
					"parameter": row["parameter"],
					"unit": row["unit"],
					"limit_text": inspections.limit_text(row),
					"reading": row["reading"],
					"reading_result": row["status"],
					"reading_result_label": row["status_label"],
				}
				for row in inspections.reading_rows(qi)
			],
		}
	)
	doc.insert()
	if previous:
		frappe.db.set_value(DOCTYPE, previous, {"certificate_status": SUPERSEDED, "superseded_by": doc.name})
	if attach_pdf:
		attach_certificate_pdf(doc.name)
		doc.reload()
	return doc


def attach_certificate_pdf(certificate: str) -> str:
	"""Render the certificate to PDF and attach it (URS-W2-017 AC-1, decision D3)."""
	from frappe.utils.pdf import get_pdf

	html = render_html(certificate)
	filename = f"{certificate}.pdf"
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": certificate,
			"attached_to_field": "pdf_document",
			"is_private": 1,
			"content": get_pdf(html),
		}
	)
	file_doc.flags.ignore_permissions = True
	file_doc.insert()
	frappe.db.set_value(DOCTYPE, certificate, "pdf_document", file_doc.file_url)
	return file_doc.file_url


# --------------------------------------------------------------------------------------
# View model incl. the embedded Trace Ribbon (URS-W2-018)
# --------------------------------------------------------------------------------------


@frappe.whitelist()
def view_model(certificate: str, levels: int | None = None) -> dict[str, Any]:
	"""German-first render model of a CoA, with the Trace Ribbon embedded (URS-W2-018).

	The ribbon is *not* snapshotted: URS-W2-018 AC-1 requires the embedded ribbon to show
	the same nodes and states as the standalone ribbon at the same instant, so it is built
	from the same `rheinwerk_mes.genealogy.ribbon.ribbon` call the Desk page uses.
	"""
	doc = frappe.get_doc(DOCTYPE, certificate)
	doc.check_permission("read")
	batch_state = frappe.db.get_value("Batch", doc.batch, "qa_state")
	return {
		"certificate": doc.name,
		"batch": doc.batch,
		"item": doc.item,
		"item_name": doc.item_name,
		"version": doc.version,
		"status": doc.certificate_status,
		"status_label": _(STATUS_LABELS.get(doc.certificate_status, doc.certificate_status)),
		"supersedes": doc.supersedes,
		"superseded_by": doc.superseded_by,
		"issue_date": _german_date(doc.issue_date),
		"inspection": doc.quality_inspection,
		"inspection_template": doc.inspection_template,
		"inspection_date": _german_date(doc.inspection_date),
		"signatory": doc.signatory,
		"signatory_name": doc.signatory_name,
		"manufacturing_date": _german_date(doc.manufacturing_date),
		"expiry_date": _german_date(doc.expiry_date),
		"qty": kg(doc.qty_original),
		"qa_state": batch_state,
		"qa_state_label": _(qa_state.STATE_LABELS.get(batch_state, batch_state or "")),
		"readings": [
			{
				"parameter": row.parameter,
				"unit": row.unit,
				"limit_text": row.limit_text,
				"reading": row.reading,
				"status": row.reading_result,
				"status_label": row.reading_result_label,
			}
			for row in doc.readings
		],
		"ribbon": ribbon.ribbon(doc.batch, levels) if levels else ribbon.ribbon(doc.batch),
		"pdf_document": doc.pdf_document,
	}


def render_html(certificate: str) -> str:
	"""The certificate body — the same markup the Desk view and the PDF use."""
	model = view_model(certificate)
	return frappe.render_template(TEMPLATE, {"coa": model})


# --------------------------------------------------------------------------------------
# Retrieval (URS-W2-019)
# --------------------------------------------------------------------------------------


@frappe.whitelist()
def certificates_for_batch(batch: str) -> list[dict[str, Any]]:
	"""Every certificate of `batch`, newest version first (URS-W2-017 AC-3)."""
	rows = frappe.get_all(
		DOCTYPE,
		filters={"batch": batch},
		fields=[
			"name",
			"batch",
			"item",
			"item_name",
			"version",
			"certificate_status",
			"issue_date",
			"signatory_name",
			"pdf_document",
		],
		order_by="version desc",
	)
	for row in rows:
		row["issue_date_label"] = _german_date(row["issue_date"])
		row["status_label"] = _(STATUS_LABELS.get(row["certificate_status"], row["certificate_status"]))
	return rows


@frappe.whitelist()
def search(term: str) -> list[dict[str, Any]]:
	"""Command-Dashboard drill-down: find CoAs by batch, item or certificate number.

	The result carries the Desk form route, so the drill-down lands in the same
	professional view the inspector uses — read-only for the business viewer, whose role
	holds no write permission on the DocType (URS-W2-019 AC-1).
	"""
	term = (term or "").strip()
	if not term:
		return []
	pattern = f"%{term}%"
	rows = frappe.db.sql(
		"""
		select name, batch, item, item_name, version, certificate_status, issue_date,
		       signatory_name, pdf_document
		from `tabCoA Certificate`
		where batch like %(term)s or item like %(term)s or name like %(term)s
		      or ifnull(item_name, '') like %(term)s
		order by version desc, modified desc
		""",
		{"term": pattern},
		as_dict=True,
	)
	results = []
	for row in rows:
		row = dict(row)
		row["issue_date_label"] = _german_date(row["issue_date"])
		row["status_label"] = _(STATUS_LABELS.get(row["certificate_status"], row["certificate_status"]))
		row["route"] = get_url_to_form(DOCTYPE, row["name"])
		row["writable"] = bool(frappe.has_permission(DOCTYPE, "write", row["name"]))
		results.append(row)
	return results
