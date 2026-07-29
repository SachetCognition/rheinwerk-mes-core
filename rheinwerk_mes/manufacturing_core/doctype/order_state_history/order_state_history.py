"""CDM-02 `state_history` audit row of a production order (URS-W1-003).

One row per `exec_state` change: the states either side of the change, the acting
user, the timestamp and the reason. Rows are written exclusively by
`rheinwerk_mes.manufacturing_core.exec_state`; every field is read-only on the form
so the audit trail cannot be edited from the Desk.

Legacy baseline (semantics only, never ported): Qcadoo
`orders/model/orderStateChange.xml:36-47` and `reasonTypeOfChangingOrderState.xml`.
"""

from __future__ import annotations

from frappe.model.document import Document


class OrderStateHistory(Document):
	pass
