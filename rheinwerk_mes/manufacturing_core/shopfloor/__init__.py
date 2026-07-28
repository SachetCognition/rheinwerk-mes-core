"""Shop-floor operator journey (W1-7 · URS-W1-026…028, URS-W1-022, URS-W1-032…035).

The journey runs on the anchor `Job Card` — never forked. Everything here either calls
anchor methods/fields or adds `rheinwerk_mes`-owned Custom Fields, defaults and assets
(`rheinwerk_mes.setup.w1_shopfloor`).

Sub-modules:

* `job_execution` — job queue, time-log start/stop, pause/resume, output recording.
* `scanner` — barcode resolution for the always-focused terminal scan field.
* `formatting` — German-first rendering (DD.MM.YYYY, kg).
* `legacy_bridge` — "was: Technology" hover affordance behind a removable flag.
* `terminal` — Desk/Terminal density tokens shared by server and page assets.
"""

from __future__ import annotations
