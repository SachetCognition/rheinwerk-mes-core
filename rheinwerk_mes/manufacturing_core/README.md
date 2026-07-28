# Manufacturing Core — Adopt (Wave W1/W3)

Anchor substrate adopted from ERPNext manufacturing: BOM + Routing (with process loss/yield), Work Order, Job Card, Workstation (finite capacity), Production Plan, shop-floor execution page.

**Absorbed on top:** recipe lifecycle governance — a 5-state approval workflow (draft → accepted → declined → outdated → checked) applied to BOM/Routing, carrying Qcadoo "technology" governance semantics.

Source lineage: ERPNext `manufacturing/*` (adopt); Qcadoo `technologies` state model (behavioural reference).
