# DEC-W3-020 (D5) — Ownership of supplier and customer master data

Decision record for programme dependency **D5** of `docs/plan/consolidation-project-plan.md`
("Business sign-off Q4: are supplier/customer masters owned by group ERP, MES holding
references only?"), raised by capability **T20** of
`docs/target-model/target-capability-model.md` and settled here because W3-3 freezes the
boundary contract that either carries partner masters or does not.

- **Status:** Accepted
- **Decision:** The **group ERP owns supplier and customer masters**. The consolidated MES
  holds a *reference* only — the `customer_ref` / partner identifier that arrives on an
  orders-in message and travels back out on the confirmation. The MES creates no partner
  record, maintains no partner attributes and publishes no partner changes.
- **Sign-off:** Sachet Agarwal — Programme Owner — 28.07.2026
- **Affects:** URS-W3-010, URS-W3-011, URS-W3-013 (contract v1.0), URS-W3-019 (register)
- **Audited by:** TC-W3-013, TC-W3-016, TC-W3-023

## Why a decision was needed

The frozen contract v1.0 has to state, per field, who is authoritative. `erp-in-001-happy.json`
carries `customer_ref: "KD-4711"`; the external-sync register (XS-01/XS-02) records the same
customer demand arriving from the group ERP. Without this decision the boundary would have to
choose at implementation time between *resolving* that reference into an ERPNext `Customer` —
making the MES a second master — and *carrying* it as an opaque key.

## Options considered

1. **MES masters partners too** (replicate customers/suppliers into ERPNext and reconcile).
   *Cost:* two systems of record for the same partner, a reconciliation obligation in both
   directions, and a divergence class (address/tax/credit changes) that no MES journey needs.
2. **Group ERP owns, MES references.** *Chosen.*
3. **MES owns, group ERP references.** Rejected outright: partner masters are driven by sales
   and procurement processes that stay in the group ERP after the consolidation; the MES sees
   only what is produced and shipped.

## Rationale

* **T20 already reads this way.** The target capability model places partner masters at the
  boundary and item/work-centre masters in the anchor — this record only makes the split
  binding for the frozen contract.
* **Fewer masters is the programme's purpose.** Consolidating three MES estates into one
  should not create a fourth partner master.
* **Nothing in W1–W3 needs partner attributes.** Planning nets against items and warehouses;
  execution books operations; dispatch prints ADR data for a batch. The only partner-shaped
  need is *which customer demand this order serves*, which a reference answers.

## Consequences

* Orders-in validates `customer_ref` as an opaque string: an unknown partner is **not** a
  rejection reason (unlike an unknown item, which is — URS-W3-010 AC-2), because the MES holds
  no partner list to check it against.
* Confirmations-out echo the same reference unchanged, so the group ERP can match without the
  MES ever interpreting it.
* No partner sync appears in the external-sync register's *carried* dispositions; partner data
  stays a group-ERP concern (URS-W3-019).
* Should a later wave need partner attributes (e.g. customer-specific labelling), it needs a
  new decision superseding this one — not an ad-hoc lookup.
