"""Apply the German-first locale baseline to sites installed before URS-W0-016.

`setup_w0()` already applies both on a fresh install and it is idempotent, but its
patch entry has long been recorded on existing sites, so the W0-016 additions get
their own entry.
"""

from __future__ import annotations

from rheinwerk_mes.setup.locale import install_locale
from rheinwerk_mes.setup.property_setters import install_shelf_life_column


def execute() -> None:
	install_locale()
	install_shelf_life_column()
