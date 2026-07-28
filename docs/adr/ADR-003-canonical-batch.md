# ADR-003: Canonical Batch entity (CDM-01)
- **Status:** Proposed (sign-off required before W2)
- **Context:** Traceability is the chemicals-critical capability and all three sources are partial: Qcadoo has a dual model (stateful genealogy Batch + warehouse Resource.batch string), ERPNext Batch is stateless master data, OFBiz Lot is an optional tag (dossier §5.2, implication 2).
- **Decision:** One canonical Batch carrying identity + QA state (Quarantined/Released/Blocked workflow) + expiry + genealogy links, deliberately designed beyond all three sources; anchor Batch DocType is the storage base, extended — never forked. Full spec: `docs/canonical-model/README.md` §CDM-01.
- **Consequences:** Migration merges Qcadoo's dual model (unmatched resource strings become identity-only batches flagged `genealogy_incomplete`); OFBiz history carries a recorded trace-boundary; blocking propagates to picking exclusion and genealogy advisories.
