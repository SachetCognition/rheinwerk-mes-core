"""The injectable OPC-UA transport and the seam for a real client (W3-5 · URS-W3-015).

No OPC-UA server exists in the programme environment and no client library is a dependency
of this app, so the transport is an interface with two implementations:

* `SimulatedTransport` — replays a committed fixture script of tag events (the plant
  simulator used by the acceptance suite and the demo stack);
* `OpcUaClientTransport` — **the seam**. It is the only place a real OPC-UA client library
  is ever imported, and the import is lazy inside `connect()`. Wiring a real plant means:

  1. add the client (`asyncua`) to the deployment's requirements — nothing else changes;
  2. implement `_subscribe()` below against `asyncua.Client`, creating one subscription per
     `OPC UA Tag Mapping.tag_address` (an OPC-UA `NodeId` string such as
     `ns=2;s=Line1.Mix01.ProducedKg`) and pushing every `datachange_notification` into
     `self._inbox` as a `TagEvent` carrying the server's `SourceTimestamp` as
     `equipment_timestamp`;
  3. keep `poll()` as-is — `ScadaAdapter` and the whole ingestion path are transport-blind.

Nothing above the transport knows how the events arrive, which is why the fixture path and
a real plant exercise identical matching, queueing and store-and-forward code.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

from rheinwerk_mes.integration.scada.contracts import TagEvent

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_FIXTURE = FIXTURE_DIR / "line1_mix01_events.json"


class TagEventTransport(Protocol):
	"""What the adapter needs from a transport: connect, hand over events, disconnect."""

	def connect(self) -> None: ...

	def poll(self) -> Iterable[TagEvent]: ...

	def disconnect(self) -> None: ...


class SimulatedTransport:
	"""Committed plant simulator: publishes a scripted sequence of tag events."""

	def __init__(self, events: Sequence[TagEvent]) -> None:
		self._inbox: deque[TagEvent] = deque(events)
		self.connected = False

	@classmethod
	def from_fixture(cls, path: str | Path = DEFAULT_FIXTURE) -> SimulatedTransport:
		payload = json.loads(Path(path).read_text(encoding="utf-8"))
		return cls([TagEvent.from_dict(entry) for entry in payload["events"]])

	def connect(self) -> None:
		self.connected = True

	def disconnect(self) -> None:
		self.connected = False

	def publish(self, event: TagEvent) -> None:
		"""Queue one further event — the test/demo hook for ad-hoc equipment behaviour."""
		self._inbox.append(event)

	def poll(self) -> list[TagEvent]:
		"""Drain everything the equipment published since the last poll, in order."""
		drained = list(self._inbox)
		self._inbox.clear()
		return drained


class OpcUaClientTransport:
	"""Live-plant transport — the documented injection point for a real OPC-UA client.

	Kept in the tree (rather than described only in prose) so the seam is type-checked and
	`ScadaAdapter(transport=OpcUaClientTransport(endpoint))` is the whole production wiring.
	"""

	def __init__(self, endpoint: str, tag_addresses: Sequence[str] = ()) -> None:
		self.endpoint = endpoint
		self.tag_addresses = tuple(tag_addresses)
		self._inbox: deque[TagEvent] = deque()

	def connect(self) -> None:
		try:
			import asyncua  # noqa: F401  — the only import of a real OPC-UA client
		except ImportError as exc:
			raise RuntimeError(
				"OPC-UA-Client-Bibliothek ist nicht installiert; "
				"für den Testbetrieb SimulatedTransport verwenden."
			) from exc
		self._subscribe()

	def _subscribe(self) -> None:
		"""Create one OPC-UA subscription per mapped tag; see the module docstring."""
		raise NotImplementedError("Live-OPC-UA-Abonnement ist in dieser Umgebung nicht implementiert (W3-5).")

	def disconnect(self) -> None:
		self._inbox.clear()

	def poll(self) -> list[TagEvent]:
		drained = list(self._inbox)
		self._inbox.clear()
		return drained
