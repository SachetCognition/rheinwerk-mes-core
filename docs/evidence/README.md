# Evidence packs

One evidence pack per wave, auto-generated at wave exit: every shipped item traced back through
disposition record → register entry → dossier finding, with source file-path citations.
This directory is the audit spine of the consolidation.

## Generator

`tools/evidence/evidence_pack.py` builds a wave-exit evidence pack from the record copies
(`docs/waves/`, `docs/urs/`, `docs/test/`) — one row per backlog item linking
item → dossier finding → URS ID(s) → test ID(s). Items missing a URS or test link are
flagged `EVIDENCE-INCOMPLETE` rather than omitted.

```
python tools/evidence/evidence_pack.py --wave W0
```

- `EVIDENCE-W0-foundation.md` — generated W0 pack (regenerate; do not edit by hand)

