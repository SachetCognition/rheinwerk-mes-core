"""Idempotent site setup owned by `rheinwerk_mes`.

Everything the app needs on top of the unmodified ERPNext substrate is created
from code here — Custom Fields, Property Setters, naming series, roles and
permissions — so that a clean `bench install-app rheinwerk_mes` produces the
same site as a migrated one. Nothing is ever created by hand on a site.

Entry points: `after_install` (see `rheinwerk_mes.install`) and the
`patches.txt` entry `rheinwerk_mes.setup.w0`.
"""

from __future__ import annotations

from rheinwerk_mes.setup.w0 import setup_w0

__all__ = ["setup_w0"]
