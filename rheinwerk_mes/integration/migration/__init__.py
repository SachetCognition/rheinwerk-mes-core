"""Master-data migration tooling (URS-W0-008…011).

Extract → import → re-export for the legacy sources; every extractor produces the same
canonical import format (`canonical.py`), which the importer lands on anchor ERPNext
DocTypes (never forked) with the source identifier preserved in `legacy_refs`.

* `extractors.erpnext_legacy` — Plant C, ERPNext DocType export (URS-W0-009)
"""
