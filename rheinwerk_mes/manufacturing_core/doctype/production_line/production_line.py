"""Production line grouping for canonical Work Centres (CDM-08, ADR-010).

Re-implements the Qcadoo `productionLines` grouping so planners can address a
line rather than an individual machine; line-level scheduling itself is W3 (T19).
Workstations link here through the `production_line` Custom Field.
"""

from __future__ import annotations

from frappe.model.document import Document


class ProductionLine(Document):
	pass
