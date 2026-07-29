# ADR-004: Canonical Production Order (CDM-02)
- **Status:** Proposed (sign-off required before W1)
- **Context:** "Order status" means three different things across sources: user-owned workflow (Qcadoo), posting-derived reflection (ERPNext), seed-data vocabulary (OFBiz) — the dossier's highest-risk semantic mismatch (§5.2).
- **Decision:** Anchor Work Order + integrity `exec_state` workflow (Pending→Accepted→In Progress→Completed/Interrupted/Abandoned/Declined) reconciled with the anchor's derived status by hooks; the unqualified word "status" is banned from canonical interfaces. Spec: CDM-02.
- **Consequences:** All Qcadoo gates become hook re-implementations under characterisation tests; OFBiz open runs map via a fixed status table at migration.
