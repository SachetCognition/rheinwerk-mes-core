"""Per-line schedule of accepted orders (W3-2 · URS-W3-005).

The document is a *plan*, not an execution record: its `schedule_state` follows the Qcadoo
`ScheduleState` machine (`scheduling.schedule_state`) and every transition goes through
`scheduling.lifecycle`, which role-gates it, capacity-checks it and audits it. Direct
writes to `schedule_state` are refused here so no caller can bypass that path.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from rheinwerk_mes.manufacturing_core.scheduling import schedule_state


class LineSchedule(Document):
	def validate(self) -> None:
		self._validate_state_value()
		self._validate_state_change()

	def _validate_state_value(self) -> None:
		if self.schedule_state not in schedule_state.STATES:
			frappe.throw(
				_("Unbekannter Planzustand: {0}").format(self.schedule_state),
				title=_("Planzustand ungültig"),
			)

	def _validate_state_change(self) -> None:
		"""Only `lifecycle` may move the state, and only along a legal edge."""
		if self.is_new():
			if self.schedule_state != schedule_state.INITIAL_STATE:
				frappe.throw(
					_("Ein neuer Linienplan beginnt im Zustand {0}.").format(
						schedule_state.state_labels()[schedule_state.INITIAL_STATE]
					),
					title=_("Planzustand ungültig"),
				)
			return

		previous = self.get_doc_before_save()
		if previous is None or previous.schedule_state == self.schedule_state:
			return
		if not self.flags.get("rheinwerk_state_transition"):
			frappe.throw(
				_("Der Planzustand wird nur über die Freigabe oder Ablehnung des Plans geändert."),
				title=_("Planzustand ungültig"),
			)
		if not schedule_state.is_legal(previous.schedule_state, self.schedule_state):
			frappe.throw(
				_("Übergang {0} → {1} ist nicht zulässig.").format(
					schedule_state.state_labels().get(previous.schedule_state, previous.schedule_state),
					schedule_state.state_labels().get(self.schedule_state, self.schedule_state),
				),
				title=_("Übergang abgelehnt"),
			)
