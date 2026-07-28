# W2-4 / W2-5 — Quality Inspection adoption and Certificates of Analysis

Scope: URS-W2-013 … URS-W2-019 (`docs/urs/URS-W2-traceability-quality.md` §3.4–3.5),
verified by TC-W2-018 … TC-W2-027 (`docs/test/TST-W2-traceability-quality.md` §3.4–3.5).
Module package: `rheinwerk_mes/quality/**`, installer `rheinwerk_mes/setup/w2_quality.py`.

Quality Inspection is an **Adopt** item: the ERPNext engine is used unmodified. The CoA is
**white space** in all three legacy systems — no parity contract exists, so its behaviour is
designed here from the URS and `rheinwerk-mes-design-SKILL.md`.

## 1. Module surface

| Module | Responsibility |
|---|---|
| `quality/inspections.py` | Estate conventions on the anchor: template lookup, creation, reading entry, the questions the gates ask |
| `quality/gates.py` | `exec_state` completion gate (URS-W2-014) and the `qa_state` release gate (URS-W2-016) |
| `quality/disposition.py` | QA disposition of a Rejected inspection + the nightly integrity check |
| `quality/queue.py` | View model of the inspector's Work Queue → Detail page |
| `quality/page/inspection_queue/**` | The Desk page (URS-W2-015) |
| `quality/coa.py`, `quality/doctype/coa_certificate/**` | Certificates of Analysis (URS-W2-017…019) |
| `quality/templates/coa_certificate.html` | One markup for the Desk view and the PDF |

## 2. Adoption decisions (URS-W2-013)

**D1 — the anchor evaluates, we never re-judge.** Parameter instantiation
(`get_item_specification_details`), numeric min/max, value match, `safe_eval` acceptance
formulae and the Accepted/Rejected result all stay in
`erpnext/stock/doctype/quality_inspection/quality_inspection.py:265-336`. `quality/` adds
no evaluation logic of its own; `enter_readings()` writes the readings and saves.

**D2 — extensions are Custom Fields and Property Setters, never a fork.** `rw_work_order`
links an inspection to its production order (an MES in-process inspection references an
order, not a stock voucher, so the anchor's `reference_type`/`reference_name` mandatory
flags are relaxed by Property Setter); `rw_unit` on `Quality Inspection Parameter` carries
the unit rendered in the queue; `rw_disposition*` carries the QA decision (§4).

**D3 — the item's template is the "inspection required" marker.** An item carrying
`quality_inspection_template` may not complete production uninspected; an item without one
is out of scope of the gate. `QIT-COMPOUND` (viscosity 1200–1400 mPa·s, density
1,02–1,06 g/cm³, moisture ≤ 0,5 %) is seeded on `RW-CHM-0003`.

**D4 — readings are stored in the site number format.** The anchor parses readings with
`parse_float`, which honours the site's number format, so `1.04` would be read as 104 on a
German site. `inspections.format_reading()` localises numeric input (`1,04`); values typed
in the queue already arrive localised and pass through untouched.

## 3. Gating (URS-W2-014)

The gate is registered through the documented hook `rheinwerk_exec_state_gates`
(`docs/design/W1-exec-state.md`); `manufacturing_core` is untouched. For every batch a
production order produced (read from the submitted stock postings) whose item carries a
template, `Completed` is refused when

* no submitted inspection exists — rule `QI-Pflichtprüfung`, or
* the inspection is Rejected — rule `QI-Ablehnung ohne Verwendungsentscheid`.

Refusals are Stop severity, name rule / record (order, batch, template or inspection) /
resolution, leave `exec_state` at `In Progress` and are written to the W1
`Execution Gate Log` via `execution_gating.audit.log_refusal`.

**D5 — a Released batch satisfies the gate.** Release is only reachable through the audited
`qa_state` machine (URS-W2-006), so a batch that is already Released carries QA evidence
even when its inspection predates the estate (migrated history, supplier certificate). The
gate therefore asks for QA evidence, not for one particular document. This also keeps the
gate from retroactively blocking historical orders on a migrated site.

An Accepted submission releases its batch through
`rheinwerk_mes.genealogy.qa_state.transition(..., triggering_document=<inspection>)` — the
genealogy child owns the state machine and the audit entry.

## 4. Rejection disposition (URS-W2-016)

A Rejected inspection offers exactly two decisions, both requiring a reason:

| Decision | German label | Effect |
|---|---|---|
| `Block Batch` | Charge sperren | `qa_state.transition(batch, BLOCKED, reason, triggering_document=<inspection>)` |
| `Assign Rework` | Nacharbeit zuweisen | records the rework production order in `rw_rework_order` |

The decision is stored on the inspection (`rw_disposition`, `rw_disposition_reason`,
`rw_rework_order`, `rw_disposition_recorded_on` — all `allow_on_submit`, all read-only in
the UI so they can only be written through `disposition.record_disposition`). Until a
decision exists, the `qa_state` gate refuses to release the batch, and
`disposition.undispositioned_rejections()` — the nightly integrity check — reports the
inspection as **„Abgelehnt ohne Verwendungsentscheid“**.

## 5. Inspector queue (URS-W2-015)

Layout pattern 1 of the design skill, *Work Queue → Detail*. The queue is filterable by
inspection type, item, batch and production order; rows carry the batch chip (ID, item,
`qa_state` pill with icon + label), the type and the due indication. Two kinds of row are
due: a draft inspection waiting for readings, and a Quarantined batch whose item carries a
template but has no inspection yet — the exact state the completion gate refuses for.

Keyboard: ↑/↓ move the selection, Enter opens the detail, Esc closes it, `?` shows the
shortcut sheet. Reading inputs carry the unit **inside** the field as a suffix
(`mPa·s`, `g/cm³`, `%`), the specification underneath, inline validation on blur; a failed
submit re-renders the pane from the entered values, never discarding them. The empty state
directs: „Keine Prüfungen fällig — Nächste geplante Prüfung: …“.

## 6. Certificate of Analysis (URS-W2-017…019)

**D6 — numbering.** `COA-.YYYY.-#####`, the estate's document-number convention: a stable,
customer-facing identifier that sorts by issue year and never reuses a number, including
across versions (a superseding certificate gets its own number, not a suffix).

**D7 — one markup, two renderings.** `quality/templates/coa_certificate.html` is rendered
both on screen and, through `frappe.utils.pdf.get_pdf`, into the attached PDF, so the
printed certificate cannot drift from the screen. Status is glyph + German label, never
colour alone.

**D8 — immutability and versioning instead of amendment.** A CoA is never edited, cancelled
or amended: the controller refuses any change to a snapshot field or reading row and refuses
deletion. A corrected result is published as a **new version**, which sets the prior
certificate to `Superseded` and links both ways (`supersedes` / `superseded_by`). Both
remain retrievable — the audit history of what was certified when is the point of the
document.

**D9 — snapshot, except the ribbon.** Readings, limits, units, batch and item identity,
signatory, issue date and batch dates/quantity are snapshotted at issue, so amending or
cancelling the source inspection cannot change what was certified. The **Trace Ribbon is
not snapshotted**: URS-W2-018 AC-1 requires the embedded ribbon to show the same nodes and
states as the standalone ribbon at the same instant, so `view_model()` calls
`rheinwerk_mes.genealogy.ribbon.ribbon` — the same function the Desk page uses.

**D10 — retention.** Certificates are retained for the full regulatory batch-record period
(10 years, `docs/urs/URS-W2-traceability-quality.md` §3.2 retention rule) and are therefore
never deleted by the app: `on_trash` refuses, and superseded versions stay in place. The PDF
is stored as a **private** File attachment, i.e. inside the site backup, and inherits the
DocType's permissions rather than being world-readable by URL.

**D11 — German-first content.** Every label on the certificate is German
(„Analysenzertifikat“, „Charge“, „Prüfmerkmal“, „Spezifikation“, „Messwert“,
„Freigebende Person“), dates are DD.MM.YYYY and the batch quantity is rendered in kg with a
decimal comma.

**D12 — retrieval for business viewers.** `coa.search(term)` matches batch, item, item name
and certificate number and returns the Desk route of each hit; the `Rheinwerk Business
Viewer` role holds `read`/`print`/`export` on `CoA Certificate` and no write permission, so
the professional view opens read-only with the PDF downloadable and without any
state-changing affordance.

## 7. Traceability

| URS | Implementation | Tests |
|---|---|---|
| URS-W2-013 | `quality/inspections.py`, seed `QIT-COMPOUND` | TC-W2-018, TC-W2-019 |
| URS-W2-014 | `quality/gates.quality_inspection_gate`, `inspections.on_inspection_submit` | TC-W2-020, TC-W2-021 |
| URS-W2-015 | `quality/queue.py`, `quality/page/inspection_queue/**` | TC-W2-022 |
| URS-W2-016 | `quality/disposition.py`, `quality/gates.rejected_inspection_gate` | TC-W2-023 |
| URS-W2-017 | `quality/coa.issue`, `CoA Certificate` | TC-W2-024, TC-W2-025 |
| URS-W2-018 | `quality/coa.view_model`, `templates/coa_certificate.html` | TC-W2-026 |
| URS-W2-019 | `quality/coa.search`, CoA permissions | TC-W2-027 |
