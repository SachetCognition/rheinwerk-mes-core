"""Post-install wiring for the `rheinwerk_mes` app."""

from __future__ import annotations

from rheinwerk_mes.setup.w0 import setup_w0


def after_install() -> None:
	"""Apply the W0 defaults on a fresh site."""
	setup_w0()
