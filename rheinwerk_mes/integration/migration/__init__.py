"""Master-data migration tooling (W0-5).

Extractors read a committed export of a legacy source and produce the canonical
import format (`canonical.py`), which the importer lands on anchor ERPNext DocTypes
(never forked) with the source identifier preserved in the legacy mapping.

* `extractors.qcadoo` — Plant A, Qcadoo PostgreSQL dump subset (URS-W0-008)
"""
