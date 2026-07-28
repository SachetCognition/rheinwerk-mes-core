"""Master-data migration tooling (W0-5, URS-W0-008…011, URS-W0-018).

Extract → import → re-export → reconcile for the three legacy sources:

* `extractors.qcadoo` — Plant A, Qcadoo PostgreSQL dump subset
* `extractors.ofbiz` — Plant B, OFBiz entity XML
* `extractors.erpnext_legacy` — Plant C, ERPNext DocType export

All three produce the same canonical import format (`canonical.py`), which the
importer lands on anchor ERPNext DocTypes (never forked) with the source
identifier preserved in the `legacy_refs` Custom Field created by
`rheinwerk_mes.setup.custom_fields`.
"""
