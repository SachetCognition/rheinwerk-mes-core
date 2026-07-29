"""Master-data migration tooling (W0-5).

`extractors.<source>.extract(path)` reads a committed legacy export and produces the
canonical import format (`canonical.py`); `importer.import_extract` lands that format on
anchor ERPNext DocTypes (`Item`, `Workstation`, `Warehouse`) — nothing is forked. Source
records that cannot be mapped are collected as exceptions and rendered by
`exceptions_report.py`; they are never imported with a defaulted value.

Delivered so far: Plant B / OFBiz (URS-W0-010). Plant A (Qcadoo, URS-W0-008) and Plant C
(ERPNext, URS-W0-009) register their own extractors against the same format.
"""
