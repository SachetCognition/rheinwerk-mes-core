"""Plant-area tree backing the canonical Work Centre `division` link (CDM-08, ADR-010).

Re-implements the Qcadoo `basic` division/plant-area hierarchy as a Frappe nested
set. It carries operational plant structure only — machine asset accounting stays
in the group ERP per ADR-002, so no asset or cost-centre fields live here.
"""

from __future__ import annotations

from frappe.utils.nestedset import NestedSet


class Division(NestedSet):
	nsm_parent_field = "parent_division"
