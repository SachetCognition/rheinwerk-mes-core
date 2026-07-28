"""CoA Certificate — the immutable analysis certificate of one batch (W2-5 · URS-W2-017).

Immutability (AC-3) is enforced here rather than by submitting the document: a CoA is never
edited, never cancelled and never amended. It is superseded by issuing a new version, which
is the only write the controller permits on an existing certificate
(`certificate_status`/`superseded_by`, set through `db_set` by
`rheinwerk_mes.quality.coa.issue`).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

ISSUED = "Issued"
SUPERSEDED = "Superseded"

#: Everything that snapshots the inspection — frozen the moment the CoA is created.
SNAPSHOT_FIELDS: tuple[str, ...] = (
	"batch",
	"item",
	"quality_inspection",
	"inspection_template",
	"inspection_date",
	"issue_date",
	"signatory",
	"version",
	"manufacturing_date",
	"expiry_date",
	"qty_original",
)


class CoACertificate(Document):
	def validate(self) -> None:
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = [field for field in SNAPSHOT_FIELDS if before.get(field) != self.get(field)]
		if changed or self._readings_changed(before):
			frappe.throw(
				_(
					"Analysenzertifikate sind unveränderlich. Für geänderte Prüfergebnisse ist "
					"eine neue Version auszustellen ({0})."
				).format(self.name),
				title=_("Änderung abgelehnt"),
			)

	def _readings_changed(self, before: Document) -> bool:
		def snapshot(doc: Document) -> list[tuple]:
			return [
				(row.parameter, row.unit, row.limit_text, row.reading, row.reading_result)
				for row in doc.get("readings") or []
			]

		return snapshot(before) != snapshot(self)

	def on_trash(self) -> None:
		frappe.throw(
			_("Analysenzertifikate werden nicht gelöscht ({0}).").format(self.name),
			title=_("Löschen abgelehnt"),
		)
