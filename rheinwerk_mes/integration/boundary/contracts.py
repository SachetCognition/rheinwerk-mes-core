"""Group-ERP boundary contract vocabulary (W3-3/W3-4 · URS-W3-010…014, ADR-002).

The boundary carries exactly the three message types ADR-002 names — *orders in*,
*confirmations out*, *GL postings out* — and nothing else: finance, buying and selling stay
permanently on the group-ERP side. This module holds the vocabulary shared by the inbound
processor, the outbound emitters, the queues, the health surface and the tests, so no
string literal describing a message type, a status or a rejection reason is duplicated.

The module is deliberately import-light (no `frappe` at module scope) so that the contract
fixture suite — which is pure schema validation — runs in the offline CI job as well as
site-backed.

Reason codes are **machine-readable** (URS-W3-010 AC-3): the code is the stable, locale-free
key an operator's tooling can branch on, while `REASON_LABELS` carries the German-first text
shown on the health surface.
"""

from __future__ import annotations

from types import MappingProxyType

#: The frozen contract version (URS-W3-013 AC-1). See `docs/design/W3-erp-boundary.md`.
CONTRACT_VERSION = "1.0"

ORDERS_IN = "orders-in"
CONFIRMATION_OUT = "confirmation-out"
GL_POSTING_OUT = "gl-posting-out"

MESSAGE_TYPES: tuple[str, ...] = (ORDERS_IN, CONFIRMATION_OUT, GL_POSTING_OUT)

INBOUND = "Eingehend"
OUTBOUND = "Ausgehend"

DIRECTIONS: MappingProxyType[str, str] = MappingProxyType(
	{
		ORDERS_IN: INBOUND,
		CONFIRMATION_OUT: OUTBOUND,
		GL_POSTING_OUT: OUTBOUND,
	}
)

# Boundary Message statuses. Terminal: PROCESSED, DELIVERED. Needing attention: REJECTED
# (error queue) and HELD (unmapped-accounts hold queue). QUEUED is the durable outbox.
PROCESSED = "Verarbeitet"
DELIVERED = "Zugestellt"
QUEUED = "In Warteschlange"
REJECTED = "Abgelehnt"
HELD = "Zurückgehalten"

STATUSES: tuple[str, ...] = (PROCESSED, DELIVERED, QUEUED, REJECTED, HELD)

#: Statuses that mean "somebody has to look at this" — the KPI tile counts these.
ATTENTION_STATUSES: tuple[str, ...] = (REJECTED, HELD)

#: Statuses that are not yet finished — the "oldest unprocessed" metric reads these.
OPEN_STATUSES: tuple[str, ...] = (QUEUED, REJECTED, HELD)

# Machine-readable reason codes.
REASON_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
REASON_UNKNOWN_ITEM = "UNKNOWN_ITEM"
REASON_UNKNOWN_WAREHOUSE = "UNKNOWN_WAREHOUSE"
REASON_UNKNOWN_UOM = "UNKNOWN_UOM"
REASON_DUPLICATE = "DUPLICATE"
REASON_UNMAPPED_WAREHOUSE = "UNMAPPED_WAREHOUSE"
REASON_ENDPOINT_UNAVAILABLE = "ENDPOINT_UNAVAILABLE"

REASON_CODES: tuple[str, ...] = (
	REASON_CONTRACT_VIOLATION,
	REASON_UNKNOWN_ITEM,
	REASON_UNKNOWN_WAREHOUSE,
	REASON_UNKNOWN_UOM,
	REASON_DUPLICATE,
	REASON_UNMAPPED_WAREHOUSE,
	REASON_ENDPOINT_UNAVAILABLE,
)

# Audit gate names written to the W1 `Execution Gate Log` (URS-W3-021).
GATE_INBOUND = "erp_boundary_inbound"
GATE_OUTBOUND = "erp_boundary_outbound"
GATE_REPLAY = "erp_boundary_replay"

MESSAGE_DOCTYPE = "Boundary Message"
DEMAND_DOCTYPE = "ERP Sales Input"
ACCOUNT_MAP_DOCTYPE = "Group ERP Account Map"


class BoundaryError(Exception):
	"""A boundary message could not be processed; carries its machine-readable reason."""

	def __init__(self, reason_code: str, message: str, *, path: str | None = None) -> None:
		super().__init__(message)
		self.reason_code = reason_code
		self.message = message
		self.path = path


def reason_labels() -> dict[str, str]:
	"""German-first labels for the reason codes (translated lazily, inside a request)."""
	from frappe import _

	return {
		REASON_CONTRACT_VIOLATION: _("Nachricht entspricht nicht dem Vertragsschema"),
		REASON_UNKNOWN_ITEM: _("Unbekannter Artikel"),
		REASON_UNKNOWN_WAREHOUSE: _("Unbekanntes Lager"),
		REASON_UNKNOWN_UOM: _("Unbekannte Mengeneinheit"),
		REASON_DUPLICATE: _("Wiederholte Zustellung (Duplikat)"),
		REASON_UNMAPPED_WAREHOUSE: _("Lager ohne Kontenzuordnung"),
		REASON_ENDPOINT_UNAVAILABLE: _("Gruppen-ERP nicht erreichbar"),
	}


def message_type_labels() -> dict[str, str]:
	"""German-first labels for the three contract message types."""
	from frappe import _

	return {
		ORDERS_IN: _("Bedarf eingehend"),
		CONFIRMATION_OUT: _("Fertigmeldung ausgehend"),
		GL_POSTING_OUT: _("Buchung ausgehend"),
	}
