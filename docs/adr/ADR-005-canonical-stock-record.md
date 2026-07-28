# ADR-005: Canonical stock-on-hand representation (CDM-03)
- **Status:** Proposed (sign-off required before W0 exit)
- **Context:** Physical-lot rows (Qcadoo Resource) vs immutable ledger+cache (ERPNext SLE/Bin) vs item records (OFBiz) — a single truth representation must be chosen (implication 4).
- **Decision:** The anchor ledger (SLE + Bin + Serial and Batch Bundle) is the only quantity truth; physical fidelity (Handling Unit, Storage Location) is layered as referencing DocTypes, never a parallel quantity store. Spec: CDM-03.
- **Consequences:** Plant A migration decomposes each Resource row into ledger + HU + location + rate with per-warehouse sum-equivalence reconciliation reports.
