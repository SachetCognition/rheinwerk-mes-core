"""Contract registry — parity contracts are enumerable by ID (URS-W0-012).

`pytest tests/characterisation` parametrises over this registry, so registering a
contract is the only step needed to add it to the regression floor. The evidence-pack
generator reads the same IDs (via the URS/TC IDs each contract declares) when it links
backlog items to tests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .api import Resolution, resolve
from .loader import load_cases

#: Signature of a contract check: (resolved implementation, fixture case) -> None.
Checker = Callable[[Resolution, Mapping[str, Any]], None]


@dataclass(frozen=True)
class Contract:
	"""One executable parity contract.

	`concern` names the adapter entrypoint (see `api.ENTRYPOINTS`) that will carry the
	W1 implementation; until it exists the contract runs against the legacy rule in
	`legacy_rules.py`.
	"""

	id: str
	title: str
	concern: str
	legacy_source: str
	fixture: str
	fallback: Callable[..., Any]
	checker: Checker
	urs_ids: tuple[str, ...]
	tc_ids: tuple[str, ...]

	def cases(self) -> list[dict[str, Any]]:
		return load_cases(self.fixture)

	def resolution(self) -> Resolution:
		return resolve(self.concern, self.fallback)

	def check(self, case: Mapping[str, Any]) -> None:
		"""Execute the contract for one fixture case; raises AssertionError on drift."""
		self.checker(self.resolution(), case)


_REGISTRY: dict[str, Contract] = {}


def register(contract: Contract) -> Contract:
	if contract.id in _REGISTRY:
		raise ValueError(f"duplicate contract id: {contract.id}")
	_REGISTRY[contract.id] = contract
	return contract


def all_contracts() -> tuple[Contract, ...]:
	"""Every registered contract, ordered by ID."""
	from . import contracts  # noqa: F401  (import for registration side effect)

	return tuple(_REGISTRY[key] for key in sorted(_REGISTRY))


def get(contract_id: str) -> Contract:
	all_contracts()
	return _REGISTRY[contract_id]
