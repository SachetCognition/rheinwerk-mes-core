"""`Recipe Governance State Change` — audit row per `gov_state` transition (URS-W1-014).

Equivalent of the Qcadoo technology state-change entity
(`SachetCognition/Chem_mes@master`, `technologies/model/technologyStateChange.xml`):
state pair, acting user, timestamp and reason.
"""

from __future__ import annotations

from frappe.model.document import Document


class RecipeGovernanceStateChange(Document):
	pass
