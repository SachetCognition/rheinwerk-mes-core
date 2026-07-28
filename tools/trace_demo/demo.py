"""The W2 trace demonstration itself — block a batch, trace both directions, render listings.

URS-W2-028 (W2-9) asks for a *scripted* scenario on the shared fixtures rather than a manual
click-through, so the same code produces the wave-acceptance artefact
(`docs/evidence/W2-trace-demo.md`) and the assertions of TC-W2-036.

The demo runs inside the caller's Frappe transaction: it blocks `BATCH-A-0002`, reads the
tree in both directions and — unless `keep_blocked` is set — releases the batch again, so it
leaves the fixture site as it found it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rheinwerk_mes.genealogy import qa_state, trace

SUPPLIER_BATCH = "SUP-K7-0001"
BLOCKED_BATCH = "BATCH-A-0002"
FINISHED_BATCHES = ("BATCH-C-1001", "BATCH-C-1002")

BLOCK_REASON = "W2-9 Nachweis: Sperrung eines Vorgängers für den Mehrstufennachweis"
RELEASE_REASON = "W2-9 Nachweis abgeschlossen — Sperrung aufgehoben"


@dataclass(frozen=True)
class Demonstration:
	"""Result of one demo run — the evidence the wave-acceptance record cites."""

	forward: dict[str, Any]
	backward: dict[str, Any]
	blocked_batch: str

	def forward_nodes(self) -> list[dict[str, Any]]:
		return [node for node in trace.flatten(self.forward) if node["level"] > 0]

	def backward_nodes(self) -> list[dict[str, Any]]:
		return [node for node in trace.flatten(self.backward) if node["level"] > 0]

	def levels(self) -> int:
		"""Deepest level reached across both directions (URS-W2-028 AC-1: at least three)."""
		nodes = trace.flatten(self.forward) + trace.flatten(self.backward)
		return max(node["level"] for node in nodes) + 1


def run(*, keep_blocked: bool = False) -> Demonstration:
	"""Block `BATCH-A-0002`, trace forward from it and backward from the first FG batch."""
	qa_state.transition(BLOCKED_BATCH, qa_state.BLOCKED, reason=BLOCK_REASON)
	try:
		demonstration = Demonstration(
			forward=trace.forward(BLOCKED_BATCH),
			backward=trace.backward(FINISHED_BATCHES[0]),
			blocked_batch=BLOCKED_BATCH,
		)
	finally:
		if not keep_blocked:
			qa_state.transition(BLOCKED_BATCH, qa_state.RELEASED, reason=RELEASE_REASON)
	return demonstration


def _row(node: dict[str, Any]) -> str:
	advisories = ", ".join(node["blocked_ancestors"]) or "—"
	return (
		f"| {node['level']} | `{node['batch']}` | {node['item']} | "
		f"{node['qty']:.3f} {node['uom']} | {node['qa_state_label']} | "
		f"{node['expiry_date'] or '—'} | {advisories} |"
	)


def render_markdown(demonstration: Demonstration) -> str:
	"""The committed artefact — deterministic, German-first, DD.MM.YYYY and kg."""
	header = "| Ebene | Charge | Artikel | Menge | QS-Status | Verfall | Gesperrte Vorgänger |\n|---|---|---|---|---|---|---|"
	forward = "\n".join(_row(node) for node in demonstration.forward_nodes())
	backward = "\n".join(_row(node) for node in demonstration.backward_nodes())
	return f"""# W2-9 — Mehrstufiger Rückverfolgungsnachweis

Erzeugt aus `tools.trace_demo` (URS-W2-028, TC-W2-036); nicht von Hand pflegen.

Gesperrte Charge: `{demonstration.blocked_batch}` · Ebenen: {demonstration.levels()}

## Vorwärts ab `{demonstration.blocked_batch}`

{header}
{forward}

## Rückwärts ab `{FINISHED_BATCHES[0]}`

{header}
{backward}
"""
