"""CDM-02 production-order state history container (URS-W0-007).

W0 ships the container only. The `exec_state` workflow that writes rows here —
Qcadoo's `OrderStateChangeService` transition set — is wave W1; nothing in W0
appends to this table, so W1 can layer the state machine without schema rework.
"""

from __future__ import annotations

from frappe.model.document import Document


class OrderStateHistory(Document):
	pass
