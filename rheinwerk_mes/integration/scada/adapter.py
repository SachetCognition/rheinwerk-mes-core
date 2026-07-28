"""The SCADA adapter runtime (W3-5 · URS-W3-015, URS-W3-017).

`ScadaAdapter` is the only moving part of the SCADA path: it pumps a transport into a sink
(by default `ingest.ingest`) and owns the store-and-forward behaviour.

* while the link to the MES is **up**, every polled event is ingested immediately;
* while it is **down** (`disconnect()`, or an ingestion that raises), the event is appended
  to the `SpoolBuffer` — the adapter keeps accepting equipment data, nothing is lost;
* `connect()` replays the spool oldest-first, marking every replayed event late and keeping
  its original equipment timestamp (URS-W3-017 AC-1).

Transport and sink are constructor arguments, so the acceptance suite runs the real runtime
against the committed simulator and a live plant only swaps the transport
(`transport.OpcUaClientTransport`).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any

from rheinwerk_mes.integration.scada.buffer import SpoolBuffer
from rheinwerk_mes.integration.scada.contracts import TagEvent
from rheinwerk_mes.integration.scada.transport import TagEventTransport

Sink = Callable[..., Any]

DEFAULT_SPOOL_NAME = "scada_opcua_spool.jsonl"


def default_spool_path() -> str:
	"""Site-private spool location; a bare directory when no site is bootstrapped."""
	try:
		import frappe

		return os.path.join(frappe.get_site_path("private", "files"), DEFAULT_SPOOL_NAME)
	except Exception:
		return os.path.join(os.getcwd(), DEFAULT_SPOOL_NAME)


class ScadaAdapter:
	"""Runtime that turns polled tag events into tracking events, outage-tolerant."""

	def __init__(
		self,
		transport: TagEventTransport,
		buffer: SpoolBuffer | None = None,
		sink: Sink | None = None,
	) -> None:
		self.transport = transport
		self.buffer = buffer if buffer is not None else SpoolBuffer(default_spool_path())
		self._sink = sink
		self.connected = True

	def sink(self, event: TagEvent, late: bool = False) -> Any:
		if self._sink is not None:
			return self._sink(event, late=late)
		from rheinwerk_mes.integration.scada import ingest

		return ingest.ingest(event, late=late)

	def disconnect(self) -> None:
		"""Simulate/handle the loss of the adapter↔MES link; equipment keeps publishing."""
		self.connected = False

	def connect(self) -> list[Any]:
		"""Restore the link and deliver everything buffered, in order, flagged late."""
		self.connected = True
		return self.replay()

	def publish(self, event: TagEvent) -> Any | None:
		"""Deliver one event, or buffer it while the MES is unreachable."""
		if not self.connected:
			self.buffer.append(event)
			return None
		try:
			return self.sink(event)
		except Exception:
			# The MES rejected the delivery — treat it as the outage it is and hold the
			# event rather than losing it (URS-W3-017).
			self.connected = False
			self.buffer.append(event)
			raise

	def replay(self) -> list[Any]:
		"""Deliver the buffered events oldest-first, marked late (URS-W3-017 AC-1)."""
		delivered: list[Any] = []
		for event in self.buffer.drain():
			delivered.append(self.sink(event, late=True))
		return delivered

	def pump(self) -> list[Any]:
		"""Poll the transport once and deliver/buffer everything it hands over."""
		return [self.publish(event) for event in self.transport.poll()]

	def run_fixture(self, events: Sequence[TagEvent]) -> list[Any]:
		"""Deliver an explicit event sequence — the demo/seed entry point."""
		return [self.publish(event) for event in events]

	@property
	def buffered(self) -> int:
		return self.buffer.depth()
