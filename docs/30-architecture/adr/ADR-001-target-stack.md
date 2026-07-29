# ADR-001: Target stack = Frappe (ERPNext manufacturing core as anchor)
- **Status:** Accepted
- **Context:** Fit-gap scoring (functional 35%, data model 20%, health 20%, extensibility 15%, UX 10%). ERPNext is golden source for quality, planning, costing, master data and extensibility, and is the healthiest codebase; Qcadoo wins genealogy/gating/recipe governance but sits on a Spring 3.x-era platform (riskiest host for new investment); OFBiz wins no capability outright.
- **Decision:** Anchor on ERPNext manufacturing/stock/quality; absorb Qcadoo semantics as hooks/workflows/DocTypes; retire OFBiz.
- **Consequences:** All Qcadoo behaviour is re-implementation (its rules live in Java listener code); characterisation tests are the parity contract.
