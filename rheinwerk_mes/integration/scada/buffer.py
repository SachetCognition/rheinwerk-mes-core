"""Adapter-side store-and-forward spool (W3-5 · URS-W3-017).

The outage this buffers is the one *between adapter and MES*, so the buffer may not live in
the MES database — it would be unreachable exactly when it is needed. It is therefore a
plain append-only JSON-lines file next to the adapter: crash-safe (each line is flushed and
fsynced), strictly ordered (append order = publication order) and frappe-free, so the
semantics are testable offline.

`drain()` reads the spool, hands the events back oldest-first and truncates the file only
after the caller consumed them without raising, so a failed replay leaves the spool intact.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from rheinwerk_mes.integration.scada.contracts import TagEvent


class SpoolBuffer:
	"""FIFO spool of undelivered tag events, persisted as JSON lines."""

	def __init__(self, path: str | os.PathLike[str]) -> None:
		self.path = Path(path)

	def append(self, event: TagEvent) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with self.path.open("a", encoding="utf-8") as handle:
			handle.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")
			handle.flush()
			os.fsync(handle.fileno())

	def events(self) -> list[TagEvent]:
		"""Buffered events, oldest first; the spool is left untouched."""
		if not self.path.exists():
			return []
		with self.path.open(encoding="utf-8") as handle:
			return [TagEvent.from_dict(json.loads(line)) for line in handle if line.strip()]

	def depth(self) -> int:
		return len(self.events())

	def drain(self) -> Iterator[TagEvent]:
		"""Yield the buffered events in order, then clear the spool.

		The spool is only cleared once the generator ran to completion, so an exception
		raised by the consumer keeps every undelivered event (URS-W3-017: nothing is lost
		at the adapter).
		"""
		events = self.events()
		yield from events
		self.clear()

	def clear(self) -> None:
		if self.path.exists():
			self.path.unlink()
