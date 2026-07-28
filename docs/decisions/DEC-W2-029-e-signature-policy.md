# DEC-W2-029 — E-signatures on compliance-critical transitions

Decision record for **URS-W2-029** (W2-10). Like `DEC-W1-030`, the `Sign-off:` line below is
machine-read: `tests/acceptance/test_w2_esignature_decision.py` (TC-W2-037) fails while it is
missing or `PENDING`, which blocks EXIT-W2-5.

- **Decision:** E-signature **required** for the three dispositive acts (QA release/block,
  CoA issue, recipe Accept); **audit trail only** for operational execution transitions.
- **Sign-off:** Sachet Agarwal — Programme Owner — 28.07.2026
- **Enforcement:** designed here, implemented in W3 —
  `docs/design/W3-esignature-enforcement.md` (URS-W2-029 AC-2 permits the split). Arming the
  enforcement switch estate-wide is a W4 cutover precondition, because the automated release
  paths must carry a signer first.

## Why a decision was needed

None of the three estates has an e-signature construct (dossier §6.3; audit findings
§E of all three chapters): Qcadoo, OFBiz and ERPNext all record *who* changed a state in an
audit trail, but none re-authenticates the actor at the point of the act or captures a
signed meaning. Consolidating three plants into one regulated estate forces the question of
which transitions need more than an audit row, because the same act will now be performed
by more users, on more plants, under one GMP/hazmat regime.

The distinction that matters is **dispositive vs operational**:

| Class | Nature | Evidence needed |
|---|---|---|
| Dispositive | Declares fitness of material or of a recipe to the outside world; hard to reverse; carried into customer documents and recalls | Signature: re-authentication + captured meaning + reason |
| Operational | Records what happened on the line; corrigible by a further posting; already fully attributed | Audit trail |

## Decision per governed transition

| Transition | Owner | E-signature | Rationale |
|---|---|---|---|
| `qa_state` Quarantined → **Released** | Quality inspector | **Required** | Releases material for consumption and for delivery — the act a recall audit reads first. |
| `qa_state` Released/Quarantined → **Blocked** | Quality inspector | **Required** | Removes stock from picking and from further genealogy use; equally consequential and must not be reversible without a named signer. |
| `qa_state` Blocked → **Released** (reversal) | Quality inspector | **Required** | The reversal of a block is the highest-risk act in the model: it returns previously rejected material to production. |
| **CoA issue** | Quality inspector | **Required** | Leaves the estate as a statement to a customer; the signer is the person certifying the results. |
| `gov_state` Checked → **Accepted** (recipe) | Technologist | **Required** | Authorises production of a chemical product to that recipe; every later batch inherits it. |
| `gov_state` → Outdated / Declined | Technologist | Audit trail | Retires a recipe; conservative direction, no material is released by it. |
| `exec_state` Pending → Accepted → In Progress → Completed / Interrupted / Stopped | Planner, operator | Audit trail | Operational record of the run; already attributed per transition with timestamp and actor (URS-W1-028), and correctable by a further transition. |
| Stocktaking / repacking postings | Warehouse | Audit trail | Ledger postings, reversible by cancellation, fully attributed by the anchor. |

Deliberate consequence: a signature is demanded exactly where material or a recipe is
*declared fit*, and nowhere else. Requiring one per job-card booking would train operators to
type their password reflexively, which weakens rather than strengthens the evidence.

## Enforcement-point design (implementation scheduled for W3)

The estate already has the two interception points needed, so no new pattern is introduced:

* **Gate hooks.** `rheinwerk_qa_state_gates` (`docs/design/W2-genealogy.md`) and the
  `exec_state`/`gov_state` gate registries (`docs/design/W1-exec-state.md`) run *before* a
  transition commits and may refuse it. A signature gate registers there and refuses the
  transition unless a valid, fresh signature accompanies it.
* **CoA issue.** The same gate runs on the CoA's own submit path
  (`docs/design/W2-quality-coa.md`).

What a signature captures — one app-owned `Electronic Signature` DocType, referenced by the
signed document, never overwritten (append-only, cancel-and-resign rather than edit):

| Field | Content |
|---|---|
| `signer` / `signer_full_name` | User re-authenticated at the moment of signing (password re-entry; no delegated or stored credential) |
| `meaning` | Fixed vocabulary, German-first: *Freigegeben*, *Gesperrt*, *Zertifiziert*, *Rezeptur genehmigt* |
| `document_type` / `document_name` / `transition` | The act being signed |
| `reason` | Mandatory free text for blocks and for block reversals |
| `signed_at` | Server timestamp (never client-supplied) |
| `payload_hash` | Hash of the signed field set, so a later edit is detectable |

Scheduled scope for W3: the `Electronic Signature` DocType, the signature gate registered on
the four required transitions, the German-first signing dialog per the design skill, and an
audit report listing signatures per batch and per CoA. Until it lands, the affected
transitions remain gated by role and recorded in their existing audit trails — W2 exits with
the decision, not with the enforcement.

**W3 addendum (delivered).** All four gates, the signing API and dialog, the append-only
record and the signature report are in `rheinwerk_mes/compliance/**`; the gates are armed by
`Rheinwerk Compliance Settings.esignature_enforced`, which ships off so the estate's
server-side release paths (inspection auto-release, QA disposition, migration loaders, fixture
seeding) can be given a signer during the W4 cutover rather than being broken mid-programme.
Rationale and evidence: `docs/design/W3-esignature-enforcement.md` §4–§5.
