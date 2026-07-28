"""SCADA / OPC-UA tracking-event adapter (W3-5 · URS-W3-015 … URS-W3-017, URS-W3-021).

White space in all three legacy systems (dossier §6.3) — designed from the URS, documented
in `docs/design/W3-scada-opcua.md`. Package layout:

* `contracts.py` — the `TagEvent` value object and the vocabularies; frappe-free.
* `buffer.py` — the adapter-side store-and-forward spool; frappe-free.
* `transport.py` — the injectable transport: the committed simulator plus the documented
  seam where a real OPC-UA client library is plugged in.
* `mapping.py` — tag → work-centre resolution over the `OPC UA Tag Mapping` DocType.
* `ingest.py` — matching, attachment to the In-Progress order, audit, unmatched queueing.
* `unmatched.py` — the planner's unmatched-events queue and its dispositions.
* `adapter.py` — the runtime that pumps a transport into `ingest`, buffering while the
  link to the MES is down and replaying in order on reconnection.
"""
