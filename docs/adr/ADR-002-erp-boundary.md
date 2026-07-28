# ADR-002: One MES app; ERP-boundary capabilities deferred across an interface
- **Status:** Accepted
- **Context:** One-vs-two gate. Planning/costing that is manufacturing-owned stays in the MES; finance, buying, selling belong to the group ERP.
- **Decision:** Single target application. Interface contract: orders in, confirmations out, GL postings out.
- **Consequences:** ERPNext's non-MES modules are fenced out of this repo; interface fixtures tested in Wave W3.
