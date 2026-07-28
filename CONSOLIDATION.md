# Consolidation traceability

Source-of-truth lineage for everything in this repository. Inputs: the *Production Systems Landscape — Reverse Engineering & Fit-Gap Dossier* and the rationalisation decision records.

| Capability area | Disposition | Golden source | Lands in module | Wave |
|---|---|---|---|---|
| BOM / routing / process loss | Adopt | ERPNext | manufacturing_core | W1 |
| Recipe lifecycle governance | Absorb | Qcadoo (5-state approval) | manufacturing_core | W1 |
| Planning / MRP / finite capacity | Adopt | ERPNext | manufacturing_core | W3 |
| Order lifecycle + hard gates | Absorb | Qcadoo listener services | execution_gating | W1 |
| Shop-floor execution UI | Adopt | ERPNext shop-floor page | manufacturing_core | W1 |
| Batch/lot master + genealogy | Absorb | Qcadoo Advanced Genealogy | genealogy | W2 |
| Batch blocking / quarantine | Absorb | Qcadoo | genealogy + warehouse | W2 |
| Quality inspection engine | Adopt | ERPNext QI | quality | W2 |
| Certificates of Analysis | Rebuild | — (white space) | quality | W2 |
| ISA-88 batch recipes | Rebuild | — (white space) | recipe_isa88 | W2 |
| Hazmat / regulatory data | Rebuild | — (white space) | regulatory_hazmat | W2/W3 |
| Warehouse physical fidelity (pallets, FEFO) | Absorb | Qcadoo material-flow-resources | warehouse | W1/W2 |
| Costing / valuation / GL posting | Adopt (boundary) | ERPNext | integration | W3 |
| SCADA / OPC-UA | Rebuild | — (white space) | integration | W3 |
| OFBiz manufacturing (all) | Retire | — | — | W4 decommission |
