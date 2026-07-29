"""Post-install wiring for the `rheinwerk_mes` app."""

from __future__ import annotations

from rheinwerk_mes.setup.w1_state_audit import setup_state_audit


def after_install() -> None:
	"""Apply the committed site setup on a fresh site."""
	setup_state_audit()
