# Legacy master-data round-trip fixtures (W0-5)

Committed, human-readable subsets of the legacy sources — the migration tooling is
**never** pointed at a live plant (`docs/test/TST-W0-foundation.md` §1, Environments).

| Plant | Source | Fixture | Format |
|---|---|---|---|
| A | Qcadoo (`SachetCognition/Chem_mes`) | `qcadoo/plant-a.sql` | `pg_dump` `COPY … FROM stdin` subset |

Content follows the programme fixture set: `RW-CHM-0001` (1 Sack = 25 kg), `RW-CHM-0002`
(1 Pail = 5 kg), `RW-CHM-0003`, warehouse "RM Lager Nord" and the Qcadoo
trigger-generated technology number `000123/2025`.
