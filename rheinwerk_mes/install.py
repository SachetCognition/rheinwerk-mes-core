"""Post-install wiring for the `rheinwerk_mes` app."""

from __future__ import annotations

from rheinwerk_mes.setup.master_data import setup_master_data


def after_install() -> None:
	"""Apply the canonical master-data extensions to the anchor DocTypes."""
	setup_master_data()
