"""Immutable audit of refused workflow transitions (W1-8 · URS-W1-029 AC-3, URS-W1-033).

Qcadoo audited every state change (`orders/model/orderStateChange.xml:36-47`); the
consolidation extends that to the *refusals*, because a hard gate is a compliance moment
(design skill § "Hard gates look hard"). Entries are written once and never edited: no
role holds write or delete rights, and the controller refuses both anyway.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class TransitionRefusalLog(Document):
	def on_update(self) -> None:
		if not self.flags.in_insert:
			frappe.throw(
				_("Auditeinträge sind unveränderlich."), frappe.PermissionError, title=_("Abgelehnt")
			)

	def on_trash(self) -> None:
		frappe.throw(
			_("Auditeinträge dürfen nicht gelöscht werden."),
			frappe.PermissionError,
			title=_("Abgelehnt"),
		)
