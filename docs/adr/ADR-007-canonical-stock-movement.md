# ADR-007: Canonical Stock Movement (CDM-05)
- **Status:** Proposed (sign-off required before W1)
- **Context:** Document-centric (Qcadoo 5 document types with acceptance semantics) vs ledger-centric (ERPNext Stock Entry) vs service-centric (OFBiz) movement models (dossier §5.2).
- **Decision:** Anchor Stock Entry purposes are canonical; Qcadoo document types map to purposes; draft-acceptance semantics are carried by reservations (ADR-008) + submit hooks, not a parallel document engine. Spec: CDM-05.
- **Consequences:** OFBiz movement history migrates as ledger entries only; Qcadoo document numbering preserved in legacy_refs.
