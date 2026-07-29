# ADR-008: Canonical Reservation (CDM-06)
- **Status:** Proposed (sign-off required before W1)
- **Context:** Reservations anchor on different objects per source: draft documents (Qcadoo), standalone 8-state entries (ERPNext), sales-order lines (OFBiz) (dossier §5.2).
- **Decision:** Anchor Stock Reservation Entry is canonical, extended with draft-document auto-reservation semantics ("draft makes reservation"); sales-order reservations stay across the ERP boundary. Spec: CDM-06.
- **Consequences:** OFBiz OrderItemShipGrpInvRes is not carried; Plant A cutover recreates open draft reservations as flagged SREs.
