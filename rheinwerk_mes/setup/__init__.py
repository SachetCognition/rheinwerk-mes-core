"""Idempotent site setup owned by `rheinwerk_mes`.

The canonical Work Centre extension on top of the unmodified ERPNext substrate is created
from code here — Custom Fields on the `Workstation` anchor — so a clean
`bench install-app rheinwerk_mes` produces the same site as a migrated one. Nothing is
ever created by hand on a site.

Entry points: `after_install` (see `rheinwerk_mes.install`) and the `patches.txt` entry
`rheinwerk_mes.setup.work_centre`.
"""

from __future__ import annotations

from rheinwerk_mes.setup.work_centre import setup_work_centre

__all__ = ["setup_work_centre"]
