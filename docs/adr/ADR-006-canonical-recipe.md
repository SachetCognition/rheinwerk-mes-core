# ADR-006: Canonical Recipe with governance (CDM-04)
- **Status:** Proposed (sign-off required before W1)
- **Context:** Qcadoo unifies BOM+routing in one governed 5-state tree; the anchor splits BOM and Routing with no approval model; OFBiz has neither governance nor unification (dossier §5.2, §5.4).
- **Decision:** Keep the anchor's BOM/Routing split; govern the pair through a `Recipe Governance` DocType (Draft→Checked→Accepted→Outdated, Declined) with structural validators and in-use locks; orders may only reference Accepted recipes. Spec: CDM-04.
- **Consequences:** Accepted BOMs become immutable-by-policy (new version + Outdated predecessor); legacy active ERPNext BOMs are backfilled as Accepted; Qcadoo technologies import as BOM+Routing pairs with their state preserved.
