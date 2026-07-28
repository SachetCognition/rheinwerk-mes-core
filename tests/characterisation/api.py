"""Contract API and target-implementation handover (URS-W0-012).

Every parity contract is evaluated through a **thin adapter**: the contract asks for a
named entrypoint inside the `rheinwerk_mes` app and falls back to the fixture-encoded
legacy rule (`legacy_rules.py`) while that entrypoint does not exist yet. When a W1 child
lands the real implementation under the documented entrypoint, the same contract starts
executing against production code with no change to the contract or its fixtures — which
is exactly the parity guarantee ADR-001 asks for.

The entrypoints W1 must implement are listed in `README.md` (§ Handover to W1) and in
`ENTRYPOINTS` below. Each target function takes the same arguments and returns the same
type as its legacy fallback.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field

#: Dotted path of the target implementation per contract concern → legacy fallback name.
ENTRYPOINTS: dict[str, str] = {
	"order_acceptance": "rheinwerk_mes.execution_gating.contracts.evaluate_order_acceptance",
	"order_completion": "rheinwerk_mes.execution_gating.contracts.evaluate_order_completion",
	"picking_order": "rheinwerk_mes.warehouse.contracts.picking_order",
	"technology_validation": "rheinwerk_mes.manufacturing_core.contracts.evaluate_technology",
	"expired_issue": "rheinwerk_mes.execution_gating.contracts.evaluate_expired_issue",
}


@dataclass(frozen=True)
class Verdict:
	"""Outcome of a legacy validation gate.

	`allowed` is False when the legacy code refuses the state transition; `errors` holds
	the Qcadoo message keys in the order the legacy code raises them.
	"""

	allowed: bool
	errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Resolution:
	"""Which implementation a contract actually ran against."""

	callable_: Callable[..., object]
	entrypoint: str
	is_target_implementation: bool

	@property
	def source(self) -> str:
		return self.entrypoint if self.is_target_implementation else "legacy fixture-encoded rule"


def resolve(concern: str, fallback: Callable[..., object]) -> Resolution:
	"""Resolve `concern` to the `rheinwerk_mes` target implementation, else to `fallback`."""
	entrypoint = ENTRYPOINTS[concern]
	module_name, _, attribute = entrypoint.rpartition(".")
	try:
		module = importlib.import_module(module_name)
	except ImportError:
		return Resolution(fallback, entrypoint, False)
	implementation = getattr(module, attribute, None)
	if not callable(implementation):
		return Resolution(fallback, entrypoint, False)
	return Resolution(implementation, entrypoint, True)
