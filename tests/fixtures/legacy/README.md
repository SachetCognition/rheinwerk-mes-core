# Legacy master-data fixtures

Committed, human-readable subsets of the legacy sources — the migration tooling is
**never** pointed at a live plant (`docs/test/TST-W0-foundation.md` §1, Environments).

| Plant | Source | Fixture | Format |
|---|---|---|---|
| C | ERPNext (`SachetCognition/Chem_erpnext`) | `erpnext/plant-c.json` | `bench export-doc`-style DocType export |

Content follows the programme fixture set: `RW-CHM-0002` (1 Pail = 5 kg), `RW-CHM-0003`,
workstation `PACK-01` and warehouse "FG Lager Süd" — the records TC-W0-010 checks for
byte-identical direct-mapped (`=`) fields.
