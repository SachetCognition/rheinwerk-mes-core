"""Source-system identifier mapping (URS-W0-003, URS-W0-014).

Every canonical record migrated from Qcadoo (Plant A), OFBiz (Plant B) or a
legacy ERPNext instance (Plant C) keeps its source identifier here instead of in
the primary key, so Frappe naming series stay platform-native while legacy
Qcadoo trigger numbers such as "000123/2025" remain queryable.
"""

from __future__ import annotations

from frappe.model.document import Document


class LegacyRef(Document):
	pass
