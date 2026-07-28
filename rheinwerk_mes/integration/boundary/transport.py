"""Injectable boundary transport (W3-3 · URS-W3-011 AC-2, ADR-002).

The group ERP does not exist in this environment, so the boundary is exercised through a
loopback transport that records what would have been sent and can be switched offline to
prove the durable queue. The transport is *injected*, never imported directly by the
emitters: W4 registers a real endpoint by pointing the `rheinwerk_boundary_transport` hook
at its own implementation, and nothing in `outbound.py` / `gl.py` changes.

A transport implements one method::

    def send(self, message: dict) -> str | None   # returns the endpoint's receipt, if any

and raises `EndpointUnavailable` when the endpoint cannot be reached. Anything else raised is
a contract or programming error and is not retried.
"""

from __future__ import annotations

import importlib
from typing import Any, Protocol, runtime_checkable

from rheinwerk_mes.integration.boundary import contracts

TRANSPORT_HOOK = "rheinwerk_boundary_transport"


class EndpointUnavailable(contracts.BoundaryError):
	"""The group-ERP endpoint could not be reached; the message stays queued."""

	def __init__(self, message: str = "Gruppen-ERP nicht erreichbar") -> None:
		super().__init__(contracts.REASON_ENDPOINT_UNAVAILABLE, message)


@runtime_checkable
class Transport(Protocol):
	def send(self, message: dict[str, Any]) -> str | None: ...


class LoopbackTransport:
	"""Records every message instead of sending it; can be taken offline.

	The recorded messages are the evidence the acceptance tests assert on (exactly one
	confirmation per completion, nothing emitted for an unmapped warehouse).
	"""

	def __init__(self, *, online: bool = True) -> None:
		self.online = online
		self.sent: list[dict[str, Any]] = []

	def send(self, message: dict[str, Any]) -> str | None:
		if not self.online:
			raise EndpointUnavailable()
		self.sent.append(message)
		return f"LOOPBACK-{len(self.sent):06d}"

	# -- test/demo controls -------------------------------------------------------------
	def go_offline(self) -> None:
		self.online = False

	def go_online(self) -> None:
		self.online = True

	def messages(self, message_type: str | None = None) -> list[dict[str, Any]]:
		if message_type is None:
			return list(self.sent)
		return [message for message in self.sent if message.get("message_type") == message_type]

	def reset(self) -> None:
		self.sent.clear()


_override: Transport | None = None
_hooked: dict[str, Transport] = {}


def transport() -> Transport:
	"""The transport in force: an explicit override or the one the hook names.

	The instance is cached per hook path, because a transport is stateful — the loopback one
	holds the messages the acceptance tests assert on, and a real endpoint holds its session.
	"""
	if _override is not None:
		return _override
	return _hooked_transport()


def _hooked_transport() -> Transport:
	path = _hook_path()
	if path not in _hooked:
		_hooked[path] = _instantiate(path)
	return _hooked[path]


def _hook_path() -> str:
	default = f"{LoopbackTransport.__module__}.{LoopbackTransport.__name__}"
	try:
		import frappe
	except ImportError:  # pragma: no cover - offline use of the module
		return default
	if not getattr(frappe.local, "site", None):
		return default
	paths = frappe.get_hooks(TRANSPORT_HOOK) or []
	return paths[-1] if paths else default


def _instantiate(path: str) -> Transport:
	module_path, _, attribute = path.rpartition(".")
	module = importlib.import_module(module_path)
	return getattr(module, attribute)()


def set_transport(replacement: Transport | None) -> None:
	"""Inject a transport (tests, W4's real endpoint); `None` restores the default."""
	global _override
	_override = replacement


def loopback() -> LoopbackTransport:
	"""The loopback transport currently in force, creating it if needed."""
	current = transport()
	if isinstance(current, LoopbackTransport):
		return current
	replacement = LoopbackTransport()
	set_transport(replacement)
	return replacement
