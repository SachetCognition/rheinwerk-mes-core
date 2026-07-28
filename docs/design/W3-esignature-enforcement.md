# W3 — Electronic-signature enforcement (DEC-W2-029 · URS-W2-029 AC-2)

W2 shipped the signed *decision* (`docs/decisions/DEC-W2-029-e-signature-policy.md`) and named
W3 as the wave that implements it. This is that implementation: the `Electronic Signature`
record, the signing API and dialog, the gates on the four dispositive acts, the signature
report, and the estate switch that arms enforcement.

## 1. What a signature is

One app-owned, append-only DocType — `Electronic Signature` (module `Compliance`):

| Field | Content |
|---|---|
| `signer` / `signer_full_name` | the re-authenticated user; the password is checked and discarded, never stored |
| `meaning` | fixed German vocabulary: *Freigegeben*, *Gesperrt*, *Zertifiziert*, *Rezeptur genehmigt* |
| `document_type` / `document_name` / `act` / `transition` | the act being signed |
| `reason` | mandatory for release and block |
| `signed_at` | server time, never client-supplied |
| `payload_hash` | SHA-256 of the signed field set |
| `consumed_by` / `consumed_at` | what the signature was spent on |

The controller refuses every edit of a stored signature except the two consumption stamps, and
refuses deletion outright. No role holds `write` or `create` on it: signatures are created only
through `esignature.sign`, which inserts with `ignore_permissions` after re-authenticating —
so the evidence cannot be manufactured or corrected by hand, only superseded by signing again.

## 2. Signing and acting are two steps

```python
esignature.sign(document_type="Batch", document_name="BATCH-A-0001",
                act=esignature.ACT_QA_RELEASE, password=…, reason=…)   # → "ESIG-2026-00001"
qa_state.transition("BATCH-A-0001", "Released", reason=…)               # the gate spends it
```

**Decision D1 — no public signature changed.** The alternative was an extra `signature=`
parameter on `qa_state.transition`, `coa.issue` and `governance.transition`. Two steps keep
every W1/W2 interface exactly as published (programme rule), and match how the UI behaves
anyway: the dialog signs, then performs the act.

**Decision D2 — the signature is a short-lived, single-use token.** Valid for
`FRESHNESS_SECONDS` (300 s), for one signer, one act and one document, and stamped consumed by
the gate that spends it. A signature therefore cannot be pre-collected in bulk, cannot be
replayed on a second act, and cannot survive a coffee break.

**Decision D3 — one act, one signature, signed where it is performed.** An accepted Quality
Inspection releases its own batch (URS-W2-014 AC-3). The inspector signs the *inspection*, and
the gate accepts that signature for the release it triggers (`alternatives=` in
`esignature.require`), rather than demanding a second signature on the batch for the same
decision. Reflexive double-signing is exactly what DEC-W2-029 warns against.

## 3. Where the gates sit

No state machine and no sibling module was edited — all three interception points already
existed:

| Act | Interception point |
|---|---|
| `qa_state` → Released / Blocked (incl. the block reversal) | `rheinwerk_qa_state_gates` hook, registered **last** so cheaper gates refuse first |
| CoA issue | `CoA Certificate.before_insert` (`doc_events`) |
| `gov_state` Checked → Accepted | `Recipe Governance.validate` (`doc_events`) |

A missing signature is refused as a gate refusal — modal, rule (`URS-W2-029`), record and
resolution — and every issued signature also writes a gate-audit entry, so the audit trail
shows the signature independently of the signature record itself.

Operational transitions (`exec_state`, stocktaking, repacking, recipe retirement) are *not*
gated, exactly as the decision records.

## 4. Enforcement is armed by an estate switch — deliberately not yet on

`Rheinwerk Compliance Settings.esignature_enforced` (default **0**). With the switch off, the
gates pass an unsigned act through; signing, the audit trail, the payload hash, the immutability
of the record and the signature report all work.

**Why.** The estate currently performs three of the four acts from *server-side* paths that have
no interactive signer: an accepted inspection releases its own batch, the QA disposition blocks
one, the W2 migration loaders set the disposition of every migrated batch, and fixture seeding
releases stock. Arming enforcement before each of those paths carries a signer would not make
the estate more compliant — it would make it unusable, and the honest place to complete that
work is the W4 cutover, where the per-plant go-live already re-examines every automated path.
The switch is therefore the deliverable, alongside proof that it refuses and permits exactly
the acts DEC-W2-029 names. Residual risk is recorded in `docs/waves/W4-cutover-decommission.md`
as a cutover precondition.

## 5. Evidence

`tests/acceptance/test_w3_esignature.py` (URS-W2-029 AC-2) covers, with enforcement armed
inside the test:

* release refused without a signature, permitted with one, and the signature stamped consumed;
* a signature is single-use and cannot be replayed on a second transition;
* an expired signature does not satisfy the gate;
* a wrong password produces no signature at all;
* block and release signatures require a reason;
* editing a stored signature and deleting one are both refused;
* an inspection-signed release satisfies the gate for the batch it releases (D3);
* CoA issue and recipe acceptance are refused unsigned and permitted signed;
* operational acts (`exec_state`) are never asked for a signature;
* every signature writes its gate-audit entry;
* the per-batch audit report spans the batch, its inspections and its certificates.
