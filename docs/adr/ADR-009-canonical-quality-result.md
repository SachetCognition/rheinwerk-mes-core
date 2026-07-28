# ADR-009: Canonical Quality Result (CDM-07)
- **Status:** Proposed (sign-off required before W2)
- **Context:** Quality result is a first-class inspection (ERPNext) vs resource flags (Qcadoo) vs a rejected-quantity number (OFBiz) (dossier §5.2).
- **Decision:** Anchor Quality Inspection is canonical; acceptance drives Batch qa_state (ADR-003); CoA Certificate (chemicals layer) is generated from accepted inspections. Spec: CDM-07.
- **Consequences:** No parametric backfill from Qcadoo/OFBiz — legacy quality flags migrate as QA-state history; CoA is net-new (white space).
