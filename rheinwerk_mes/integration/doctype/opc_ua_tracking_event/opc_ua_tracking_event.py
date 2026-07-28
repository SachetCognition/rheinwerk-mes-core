"""OPC UA Tracking Event — the ingested process-control event (W3-5 · URS-W3-015).

The row is the tracking record of one equipment value change: written by
`rheinwerk_mes.integration.scada.ingest`, never by hand (`in_create`), and read by the
unmatched-events queue and the order's event history.
"""

from __future__ import annotations

from frappe.model.document import Document


class OPCUATrackingEvent(Document):
	pass
