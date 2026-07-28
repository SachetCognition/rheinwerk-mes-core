"""OPC UA Tag Mapping — technologist-maintained tag administration (W3-5 · URS-W3-016)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from rheinwerk_mes.integration.scada.contracts import EVENT_TYPES
from rheinwerk_mes.integration.scada.mapping import resolve_work_centre


class OPCUATagMapping(Document):
	def validate(self) -> None:
		self.tag_address = (self.tag_address or "").strip()
		if self.event_type not in EVENT_TYPES:
			frappe.throw(
				_("Ereignisart {0} ist nicht bekannt.").format(self.event_type),
				title=_("Zuordnung abgelehnt"),
			)
		resolved = resolve_work_centre(self.work_centre_code)
		self.work_centre_code = resolved["work_centre_code"]
		self.production_line = resolved["production_line"]
		self.work_centre = resolved["work_centre"]
