# DEC-W1-030 — Estate-wide expiry policy: hard stop

Decision record for **URS-W1-030** (W1-9). This file is the machine-read source of the
sign-off: `tools/behaviour` parses the `Sign-off:` line below and refuses to generate the
per-gate behaviour record — and therefore blocks W1 exit — while it is missing or `PENDING`
(URS-W1-030 AC-3, URS-W1-031 AC-2).

- **Decision:** Hard stop. Consuming or allocating a batch past its expiry date is refused
  estate-wide, on every plant, for every posting route.
- **Sign-off:** Sachet Agarwal — Programme Owner — 28.07.2026
- **Verdict against Plant A:** Intentional divergence
- **Contract:** `CHAR-EXPIRY-ISSUE-01`

## Why a decision was needed

The three estates disagree:

| Estate | Behaviour on expired stock | Source |
|---|---|---|
| Plant A — Qcadoo | **Advisory.** FEFO/LEFO *order* candidate resources by `expirationDate`, but the issue path never compares expiry to the posting date, so an expired resource is issuable. | `ResourceManagementServiceImpl.java:1015-1027`, `:236-330` |
| Plant B — OFBiz | Advisory. Expiry is master data on the lot; no issue-time refusal. | dossier §5.4 |
| Substrate — ERPNext | **Hard stop** on posting an expired batch — with gaps: `validate_batch` skips its throw for `voucher_type == "Stock Entry"`, and the bundle service skips `BatchExpiredError` for *Material Issue* / *Material Transfer*. | `stock_ledger_entry.py:287-299`, `stock/services/serial_batch_bundle_service.py:110-112` |

Consolidation onto one estate cannot keep both readings: the same batch would be
consumable at Plant A and refused at Plant C.

## Decision and rationale

The estate adopts the **hard stop**, extended to close the substrate's own gaps:

* a chemical batch past its shelf life is not fit for a compound that carries the batch's
  genealogy into a customer CoA — the compliance and recall exposure of a silent issue
  outweighs the convenience of the legacy workaround;
* the substrate already refuses in most routes, so hard stop is the smaller net change and
  never *weakens* an anchor rule — the app only ever refuses more;
* W2 provides the legitimate escape hatch: an expired batch is dispositioned through
  quality release (`qa_state`), which is an auditable act by a named inspector, rather than
  an unrecorded operator decision at the point of issue.

## Implementation

| Route | Enforcement |
|---|---|
| Automatic allocation (FEFO/LEFO/FIFO/LIFO) | `rheinwerk_mes.execution_gating.allocation.allocate_under_expiry_policy` — expired batches are skipped; the allocation is refused when unexpired stock cannot cover demand |
| Stock Entry posting | `rheinwerk_mes.execution_gating.expiry.enforce_batch_expiry` (`Stock Entry.validate`) |
| Pick List | substrate rule `pick_list.py:286-311` (`validate_expired_batches`), verified only |
| Screens | `allocation.allocation_view` returns a signal state per resource: red once expired, amber within `EXPIRING_SOON_DAYS` (30) |

Refusals are hard-gate modals naming *Regel / Datensatz / Behebung* and are logged
immutably to `Execution Gate Log` (URS-W1-033).

## Consequences

* `CHAR-EXPIRY-ISSUE-01` fails against the target by design; the harness runs its
  divergent case as a strict xfail and the behaviour record classifies it as **Divergence**
  linked to this record — a parity failure is therefore still a real failure everywhere
  else (URS-W1-031 AC-3).
* Plant A operators lose an undocumented workaround. Migrated master data with stale expiry
  dates can stop a line; the W4 cutover checklist therefore has to review expiry dates on
  migrated batches before go-live.
* Expired stock still needs a disposition path — delivered in W2 (`qa_state`, quarantine
  locations), not in W1.
