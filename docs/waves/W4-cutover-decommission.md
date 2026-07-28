# Wave W4 — Cutover & Decommission

Per-plant cutover by journey; data backfill; legacy systems read-only then archived (Qcadoo, legacy ERPNext instance, OFBiz).

**Exit:** all personas on target; decommission complete.

## Backlog

| # | Item | Disposition / golden source | Dossier finding (evidence) |
|---|---|---|---|
| W4-1 | Per-plant cutover runbooks by journey (Plant A Qcadoo, Plant B OFBiz, Plant C legacy ERPNext instance) | — | Journey comparison §5.3 |
| W4-2 | Plant A data backfill: decompose lot-level `Resource` rows into target batch/bundle/bin representation preserving pallet/location/expiry/price | Absorb migration | ch. 3.1 `ResourceFields.java:32-90`; §7 implication 4 |
| W4-3 | Plant B backfill: parties/products/inventory balances/open production runs from OFBiz; record genealogy trace-boundary date for optional-lot history | Retire OFBiz | ch. 3.3 `product-entitymodel.xml:1967,2419`; §7 implication 9 |
| W4-4 | Plant A genealogy backfill from TrackingRecords incl. archived (`arch_*`) orders | Absorb migration | ch. 3.1 `mes_db_en.sql:292-648` archiving machinery |
| W4-5 | Legacy read-only period: freeze legacy writes, keep query access; then archive | — | Wave definition |
| W4-6 | Archive Qcadoo build artefacts + `nexus.qcadoo.org` snapshot dependencies before decommission (build unreproducibility risk) | — | §7 implication 10; ch. 3.1 §E |
| W4-7 | Decommission evidence pack: per-plant persona sign-off, data-reconciliation reports, trace-boundary register | — | Wave exit criterion |
| W4-8 | Arm estate-wide e-signature enforcement (`Rheinwerk Compliance Settings.esignature_enforced`): every automated release path — accepted inspection releasing its batch, QA disposition, migration loaders, fixture seeding — must carry a named signer first | W3 delivery, `docs/design/W3-esignature-enforcement.md` §4 | DEC-W2-029 (signed) |
