"""Immutable log of every gated action (W1-2 · URS-W1-033).

One row per gate decision: the rule that judged, the record it judged, the user, the
timestamp and the outcome (refusal or executed transition). Rows are written by
`rheinwerk_mes.execution_gating.audit` only and can never be edited or deleted
afterwards — the compliance requirement behind TC-W1-036 step 2.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ExecutionGateLog(Document):
	"""Append-only audit entry; every mutation after insert is refused."""

	def validate(self) -> None:
		if not self.is_new():
			frappe.throw(
				_("Protokolleinträge des Ausführungs-Gates sind unveränderlich (Eintrag {0}).").format(
					self.name
				),
				frappe.PermissionError,
				title=_("Änderung abgelehnt"),
			)

	def on_trash(self) -> None:
		frappe.throw(
			_("Protokolleinträge des Ausführungs-Gates dürfen nicht gelöscht werden (Eintrag {0}).").format(
				self.name
			),
			frappe.PermissionError,
			title=_("Löschen abgelehnt"),
		)
