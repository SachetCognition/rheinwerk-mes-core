# Legacy master-data round-trip fixtures (W0-5)

Committed, human-readable subsets of the three legacy sources — the migration tooling is
**never** pointed at a live plant (`docs/test/TST-W0-foundation.md` §1, Environments).

| Plant | Source | Fixture | Format |
|---|---|---|---|
| A | Qcadoo (`SachetCognition/Chem_mes`) | `qcadoo/plant-a.sql` | `pg_dump` `COPY … FROM stdin` subset |
| B | OFBiz (`SachetCognition/VM_ofbiz-framework`) | `ofbiz/plant-b-entities.xml` | entity-engine XML export |
| C | ERPNext (`SachetCognition/Chem_erpnext`) | `erpnext/plant-c.json` | `bench export-doc`-style DocType export |

Content follows the programme fixture set: `RW-CHM-0001` (1 Sack = 25 kg), `RW-CHM-0002`
(1 Pail = 5 kg), `RW-CHM-0003`, one OFBiz machine `FixedAsset` (imports as a Workstation
only — CDM-08), warehouse "FG Lager Süd" and the Qcadoo trigger number `000123/2025`.

`ofbiz/plant-b-entities.xml` deliberately contains one Product with an unmappable unit of
measure (`WT_lb`); it must land in the exceptions report, never be silently defaulted
(URS-W0-010 AC-2).

The FAIL path (URS-W0-011 AC-2, TC-W0-012 step 2) is exercised by renaming an imported
record in the target after the import and re-running the reconciliation, so the negative
case stays a property of the tooling rather than of a second, drift-prone fixture copy.
