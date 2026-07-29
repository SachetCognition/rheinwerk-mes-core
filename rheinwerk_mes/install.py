"""Post-install wiring for the `rheinwerk_mes` app."""

from __future__ import annotations

from rheinwerk_mes.setup.w1_exec_state import setup_w1_exec_state


def after_install() -> None:
	"""Install the production-order `exec_state` artefacts on a fresh site."""
	setup_w1_exec_state()
