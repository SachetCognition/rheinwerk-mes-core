# ADR-010: Canonical Work Centre (CDM-08)
- **Status:** Proposed (sign-off required before W0 exit)
- **Context:** Machines are workstations in production-line/division trees (Qcadoo), capacity-bearing workstations (ERPNext), or accounting fixed assets (OFBiz) (dossier §5.2).
- **Decision:** Anchor Workstation (+Type) is canonical, extended with production_line and division links; the operational resource (MES) is separated from the asset ledger (group ERP). Spec: CDM-08.
- **Consequences:** OFBiz machine FixedAssets import as Workstations only; asset accounting stays with group ERP; production_line grouping underpins W3 finite-capacity scheduling.
