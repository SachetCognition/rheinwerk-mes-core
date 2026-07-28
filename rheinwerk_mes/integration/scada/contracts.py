"""Vocabulary and the wire shape of an OPC-UA tag event (W3-5 · URS-W3-015 … URS-W3-017).

Deliberately frappe-free: the adapter half of the SCADA path (transport, spool buffer,
ordering, late flagging) is exercised offline, without a site, so the store-and-forward
semantics are testable exactly where they run — outside the MES process.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: The source system every OPC-UA-originated record is attributed to — never an operator
#: (URS-W3-015 AC-1). Also the actor of the audit entry (URS-W3-021).
SOURCE_SYSTEM = "OPC-UA"

#: The service account the adapter acts as, so the gate audit's actor *is* the source
#: system rather than whichever user happened to trigger the pump (URS-W3-021).
SOURCE_SYSTEM_USER = "opcua@rheinwerk-chemie.example"

EVENT_OPERATION_START = "operation-start"
EVENT_OPERATION_STOP = "operation-stop"
EVENT_PRODUCED_COUNT = "produced-count"

EVENT_TYPES = (EVENT_OPERATION_START, EVENT_OPERATION_STOP, EVENT_PRODUCED_COUNT)

#: Lifecycle of an `OPC UA Tracking Event` row (German-first, per ADR-004 the word
#: "status" is never used for a state vocabulary).
STATE_PROCESSED = "Verarbeitet"
STATE_UNMATCHED = "Nicht zugeordnet"
STATE_ASSIGNED = "Zugeordnet"
STATE_DISCARDED = "Verworfen"

EVENT_STATES = (STATE_PROCESSED, STATE_UNMATCHED, STATE_ASSIGNED, STATE_DISCARDED)

#: URS-W3-015 AC-1 — attachment budget for one event, measured per ingestion.
ATTACHMENT_BUDGET_SECONDS = 5.0

WORK_CENTRE_CODE_SEPARATOR = "/"


@dataclass(frozen=True)
class TagEvent:
	"""One value change published by plant equipment on an OPC-UA node.

	`equipment_timestamp` is the *equipment's* clock (ISO 8601 string) and is carried
	through unchanged, whether the event is delivered live or replayed after an outage
	(URS-W3-017). `sequence` is the adapter's monotonic publication counter and is what
	replay ordering is asserted on.
	"""

	tag_address: str
	value: float
	equipment_timestamp: str
	sequence: int = 0
	meta: dict[str, Any] = field(default_factory=dict)

	def as_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, payload: dict[str, Any]) -> TagEvent:
		return cls(
			tag_address=payload["tag_address"],
			value=float(payload.get("value") or 0.0),
			equipment_timestamp=payload["equipment_timestamp"],
			sequence=int(payload.get("sequence") or 0),
			meta=dict(payload.get("meta") or {}),
		)
