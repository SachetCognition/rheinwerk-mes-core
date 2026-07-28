"""Characterisation harness — executable Qcadoo parity contracts (W0-6, URS-W0-012).

The harness is the programme's regression floor: every contract encodes one piece of
legacy Qcadoo behaviour, cites the Java source it was read from, and executes against
committed fixture data. Contracts run offline (no Frappe site) so they gate every CI run.
"""
