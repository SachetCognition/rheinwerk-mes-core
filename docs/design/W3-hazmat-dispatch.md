# W3-6 — Hazmat dispatch: ADR transport data and label output

**URS:** URS-W3-018 · **TC:** TC-W3-021, TC-W3-022 · **Module track:** `regulatory_hazmat`

W2-7 delivered hazmat **master data**: an app-owned `Hazmat Profile` (UN number, SDS
reference, TRGS 510 Lagerklasse, CLP statements) linked to the anchor `Item` and `Batch` by
custom fields, with the hazmat chip on the anchor forms and the Trace Ribbon
(`docs/design/W2-hazmat.md`). W3-6 completes that profile at the **shipping boundary**: ADR
transport data, dispatch label data for finished-goods batches, and a gate that refuses
dispatch while the transport data is incomplete.

White space in all three legacy systems (dossier §6.3) — Qcadoo, ERPNext and OFBiz carry no
dispatch/ADR behaviour to absorb, so there is no parity contract. Everything below is designed
from the URS, from the regulation it names (ADR) and from `rheinwerk-mes-design-SKILL.md`.

## 1. Two axes, one profile

The URS says "extend the profile", and the two classifications must not be conflated:

| Axis | Regulation | Field | Meaning |
|---|---|---|---|
| Storage | TRGS 510 | `storage_class` (W2-7) | how the substance may be **stored** (Lagerklasse) |
| Transport | ADR Teil 2 | `adr_class` (W3-6) | how it may be **carried** (Gefahrgutklasse) |

They frequently differ (a corrosive is ADR class 8 but Lagerklasse 8A/8B), so `adr_class` is a
separate field with its own vocabulary (`contracts.ADR_CLASSES`) and its own German
designation, and the label prints both. Packing group (`adr_packing_group`, ADR 2.1.1.3) is
likewise its own field — a degree of danger, not a storage attribute.

Fields added to the existing `Hazmat Profile` (no new DocType, no parallel profile):

| Field | Type | Note |
|---|---|---|
| `adr_class` | Select | ADR Teil 2 class list, 1 … 9 incl. 4.1/4.2/4.3/5.1/5.2/6.1/6.2 |
| `adr_class_designation` | Data, read-only | derived German designation — never a bare code on screen |
| `adr_packing_group` | Select | I / II / III |
| `adr_tunnel_code` | Data | ADR 3.2.1 column 15, e.g. `D/E`; optional |
| `adr_label_numbers` | Data | Gefahrzettel numbers, ADR 5.2.2; optional |
| `adr_dispatch_ready` | Check, read-only | derived: exactly the dispatch gate's verdict |

The UN number and the proper shipping name the URS lists are already W2-7 fields and are
re-used unchanged; the shipping name is now rendered as ADR 3.1.2 requires on documents (upper
case, `contracts.shipping_name`) instead of being stored twice. All four ADR fields the URS
names are version-audited on change (`AUDITED_FIELDS`), like the W2 regulatory fields.

### Decision 1 — incomplete transport data is *saveable*, dispatch is where it bites

TC-W3-022's precondition is a hazmat item "whose profile lacks a UN number", so incomplete
profiles must be able to exist. The alternative (refuse the save) would move the refusal to
the technologist's desk and make the URS's dispatch refusal unreachable. Therefore:

* the profile controller validates the **shape** of whatever ADR data is present (an unknown
  class or packing group is still refused — garbage is never storable), but does not require
  the transport fields; the W2 requirement on `un_number` and `storage_class` is left exactly
  as W2-7 set it (that suite is untouched and still green);
* the **completeness** rule lives once, at the boundary, in
  `regulatory_hazmat.dispatch.enforce_adr_completeness`;
* `adr_dispatch_ready` mirrors that verdict read-only onto the profile, so the technologist
  sees the gap on the master record instead of discovering it when a lorry is at the gate.

The AC-2 fixture (`RW-CHM-0004` / `HAZ-RW-CHM-0004`) is therefore created *through* the
controller with a UN number and then emptied at database level: the fixture is the gap a
migrated record has, not a way around the rule.

### Decision 2 — "complete" means all four fields ADR 5.4.1.1.1 names

`contracts.ADR_REQUIRED_FIELDS` = UN number, proper shipping name, ADR class, packing group —
the four the URS lists, in the order the transport document requires them. Tunnel code and
Gefahrzettel are printed when maintained but never gate dispatch: ADR only demands the tunnel
code for carriage through restricted tunnels, so requiring it would refuse lawful shipments.

## 2. The dispatch gate

"Dispatch" is the outward movement of finished goods to a third party:

* `Stock Entry` with purpose **Material Issue** or **Send to Subcontractor**
  (`dispatch.DISPATCH_PURPOSES`), rows with a source warehouse;
* `Delivery Note` — the other half of the same boundary.

Internal transfers, transfer for manufacture, manufacture and repack are *not* dispatch: they
stay inside the estate and are already governed by the W1/W2 gates (expiry, blocked batch,
quarantine exit). Batch resolution reads `batch_no` or the row's
`serial_and_batch_bundle`, so bundled postings are gated identically.

Registration follows W1-3's expiry hard stop exactly: a `validate` `doc_events` hook in
`hooks.py` (append-only), appended *after* the existing gates so allocation has already chosen
its batches. `execution_gating/**` is read and consumed, never edited:

* the refusal is written to the shared, immutable `Execution Gate Log` through
  `execution_gating.audit.log_refusal` (gate `hazmat_dispatch_gate`, outcome *Abgelehnt*,
  reference = the offending `Batch`, detail = the missing fields);
* the `rheinwerk_exec_state_gates` registry is deliberately **not** used: that registry gates
  production-order *state transitions*, and a dispatch is a stock posting. This is the same
  reason the W1 expiry stop is a document hook and not a registry entry, so the gating
  mechanism does express this guard — through its document-hook half.

One small friction worth noting for a later cleanup: `execution_gating.expiry._row_batches` is
module-private, so `dispatch._row_batches` re-reads the same two row shapes. Publishing that
helper (a change inside `execution_gating/**`, out of this item's footprint) would let both
gates share one reader.

### Refusal presentation

Modal-grade (`frappe.throw` → Desk modal / Terminal gate card), never a toast, and it names
the three parts the URS demands, German-first via `frappe._()`:

* **Regel:** "Gefahrgut darf nur mit vollständigen ADR-Transportdaten versandt werden
  (UN-Nummer, offizielle Benennung, ADR-Klasse, Verpackungsgruppe)."
* **Datensatz:** item, batch, profile and the missing fields by their German labels.
* **Behebung:** "Gefahrstoffprofil vervollständigen (Technologe, Feld „ADR-Transportdaten“)
  und den Versand erneut buchen."

Every offending batch is logged separately, so the audit trail names records, not documents.

## 3. Label data

`labels.label_model(batch, warehouse=None, handling_unit=None, qty=None)` is the single label
model; `labels.dispatch_label_html` renders it through
`regulatory_hazmat/templates/dispatch_label.html`. Screen preview and paper label use the
**same** template (the W2-5 CoA rule), so what the clerk approves is what the drum carries.

The label is derived data, never a new store:

* hazmat values come from `profiles.effective_profile(batch=…)` — the W2-7 resolver, item
  profile with batch override, so a repacked batch keeps its own profile and a corrected
  profile corrects every label printed afterwards;
* **net quantity** is the anchor ledger balance of the batch in the dispatch warehouse
  (`warehouse.availability.ledger_balance`, expired stock included so a label can still be
  produced for disposal transport), formatted in kg with the German decimal separator
  (`format_kg` → `200,000 kg`). `qty` overrides it for a partial dispatch of one handling
  unit; the model never stores a quantity of its own;
* the dispatch warehouse defaults to `Batch.warehouse` where the substrate has it, else the
  ledger warehouse holding the most of the batch;
* dates are DD.MM.YYYY (`format_date_de`), class and packing group always carry their German
  designation, and `transport_document_line` renders the ADR 5.4.1.1.1 sequence
  (`UN 1263, FARBE, 3, III, (D/E)`) for the transport document;
* `complete` / `missing` / `missing_labels` carry the same verdict as the gate, so the preview
  shows the refusal before the goods are on the loading bay.

## 4. Dispatch station (Terminal mode)

Page `dispatch-label` ("Versandetikett Gefahrgut"), Terminal Card pattern, Terminal mode by
default because the station is a shop-floor workplace:

* the Terminal tokens of `public/css/shopfloor.css` (`--rw-target: 48px`, 18 px base) are
  reused, not re-invented; `hazmat_dispatch.css` only adds the preview layout and the gate
  card. F2 switches density — Terminal mode enlarges, it never hides;
* an always-focused scan field is the primary input: `dispatch.resolve_dispatch_scan` reuses
  the existing W1 resolver (`manufacturing_core.shopfloor.scanner.resolve` — orders, job
  cards, batches, items) unchanged and adds the one leg it does not know, the W2-8 handling
  unit by barcode, so scanning `HU-000123` resolves the unit and the batch standing on it.
  `scan_for_dispatch` returns resolution *and* label data in one round trip and reports
  `server_ms` against the ≤ 300 ms scan budget;
* one giant primary action (print), disabled while the ADR data is incomplete, with the
  refusal shown as a persistent gate card naming rule/record/resolution;
* `@media print` drops the station chrome so only the label goes on paper.

Fixtures: `HU-000125` is a finished-goods handling unit carrying BATCH-C-1001 out of
`FG Lager Süd - RWC`; `HU-000123` (W2-8, raw-material pallet) still resolves through the same
scan path.

## 5. Traceability

| URS | AC | Implementation | TC |
|---|---|---|---|
| URS-W3-018 | AC-1 | `labels.label_model` / `dispatch_label.html`, ADR fields on `Hazmat Profile`, `dispatch.resolve_dispatch_scan` | TC-W3-021 |
| URS-W3-018 | AC-2 | `dispatch.enforce_adr_completeness` + `execution_gating.audit.log_refusal`, `hooks.py` registration | TC-W3-022 |

Tests: `tests/acceptance/test_w3_hazmat_dispatch_label.py`,
`tests/acceptance/test_w3_hazmat_dispatch_guard.py`.
Installer: `rheinwerk_mes/setup/w3_hazmat.py` (`after_install` + `patches.txt`), idempotent —
it reloads the extended profile DocType and backfills the two derived fields.
