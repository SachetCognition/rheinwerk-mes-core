"""`Hazmat Profile` — the regulatory master-data record (W2-7 · URS-W2-023).

App-owned DocType: the anchors (`Item`, `Batch`) only gain a Link Custom Field to it, so no
anchor is forked (programme rule 1, installer `rheinwerk_mes/setup/w2_hazmat.py`).

The controller keeps the profile regulatorily well-formed (UN number, Lagerklasse per
TRGS 510, CLP statement codes — `regulatory_hazmat.contracts`), derives the German
Lagerklasse designation, and writes the field-level revision audit URS-W2-023 AC-3 demands
(user, timestamp, before/after) into the `revisions` child table. White space in all three
legacy systems (dossier §6.3) — no parity contract exists; design note
`docs/design/W2-hazmat.md`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from rheinwerk_mes.regulatory_hazmat import contracts

#: Fields whose change is version-audited (URS-W2-023 AC-3). The SDS reference is the one
#: the URS names explicitly; the other three carry the same regulatory weight.
AUDITED_FIELDS: tuple[str, ...] = (
	"un_number",
	"storage_class",
	"sds_reference",
	"sds_version",
	"sds_revision_date",
	"water_hazard_class",
	"signal_word",
)


class HazmatProfile(Document):
	def validate(self) -> None:
		self._normalise()
		self._audit_changes()

	def _normalise(self) -> None:
		try:
			self.un_number = contracts.normalise_un_number(self.un_number)
			self.storage_class = contracts.validate_storage_class(self.storage_class)
			for statement in self.statements:
				statement.code = contracts.validate_statement_code(statement.code, statement.statement_type)
		except contracts.HazmatDataError as error:
			frappe.throw(str(error), title=_("Gefahrstoffprofil unvollständig"))
		self.storage_class_designation = _(contracts.STORAGE_CLASSES[self.storage_class])
		for pictogram in self.pictograms:
			pictogram.designation = _(contracts.GHS_PICTOGRAMS.get(pictogram.pictogram, ""))
		if not self.revision:
			self.revision = 1

	def _audit_changes(self) -> None:
		"""Append one revision row per changed regulatory field (before/after, who, when)."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changes = [
			(field, before.get(field), self.get(field))
			for field in AUDITED_FIELDS
			if str(before.get(field) or "") != str(self.get(field) or "")
		]
		if not changes:
			return
		self.revision = (self.revision or 1) + 1
		timestamp = now_datetime()
		for field, value_before, value_after in changes:
			self.append(
				"revisions",
				{
					"revision": self.revision,
					"changed_field": field,
					"value_before": str(value_before or ""),
					"value_after": str(value_after or ""),
					"changed_by": frappe.session.user,
					"changed_on": timestamp,
				},
			)
