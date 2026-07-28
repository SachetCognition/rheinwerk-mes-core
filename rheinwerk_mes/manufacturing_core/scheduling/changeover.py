"""Line changeover norms (W3-2 · URS-W3-007).

Re-implemented — never ported — from `SachetCognition/Chem_mes@master`
`mes-plugins/mes-plugins-line-changeover-norms/src/main/java/com/qcadoo/mes/
lineChangeoverNorms/ChangeoverNormsSearchServiceImpl.java:48-64` (`findBestMatching`) and
`:66-103` (the line and product-pair restrictions). Legacy precedence, kept verbatim:

1. only norms of the sequenced line or line-agnostic norms are candidates (`:66-71`);
2. the more specific changeover type wins — a norm naming both products before a norm
   naming a product group / any successor (`:57`, `ChangeoverType`);
3. a line-specific norm beats a line-agnostic one (`:59`);
4. on a remaining tie the newest norm wins (`:61`).

When nothing matches, the legacy search returns null and no changeover time is inserted;
the transition is annotated with `NO_NORM_NOTE` so the absence is visible on the board
rather than silent (URS-W3-007 AC-2).

Pure functions over plain mappings — `norms.py` loads the `Line Changeover Norm` rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: Machine-readable annotation of a transition without a norm (URS-W3-007 AC-2). The board
#: renders it through the German-first glossary in `board.py`.
NO_NORM_NOTE = "no changeover norm"

#: Changeover specificity, most specific first — Qcadoo `ChangeoverType` ordering (`:57`).
SPECIFIC_PAIR = "specific"
ANY_SUCCESSOR = "any"

_SPECIFICITY: dict[str, int] = {SPECIFIC_PAIR: 0, ANY_SUCCESSOR: 1}


def _matches(norm: Mapping[str, Any], from_item: str, to_item: str, production_line: str | None) -> bool:
	line = norm.get("production_line")
	if line and production_line and line != production_line:
		return False
	if norm.get("from_item") != from_item:
		return False
	to_norm = norm.get("to_item")
	if to_norm:
		return to_norm == to_item
	# No successor named: the norm covers "to any other product" (`ChangeoverType` group case).
	return to_item != from_item


def _sort_key(norm: Mapping[str, Any]) -> tuple[int, int, int]:
	specificity = _SPECIFICITY[SPECIFIC_PAIR if norm.get("to_item") else ANY_SUCCESSOR]
	line_specific = 0 if norm.get("production_line") else 1
	# Newest wins: the loader passes `sequence` ascending, so invert it.
	return (specificity, line_specific, -int(norm.get("sequence") or 0))


def best_matching(
	norms: Sequence[Mapping[str, Any]], from_item: str, to_item: str, production_line: str | None = None
) -> Mapping[str, Any] | None:
	"""The norm the legacy search would return, or None (`findBestMatching`, :48-64)."""
	candidates = [norm for norm in norms if _matches(norm, from_item, to_item, production_line)]
	if not candidates:
		return None
	return sorted(candidates, key=_sort_key)[0]


def changeover_minutes(
	norms: Sequence[Mapping[str, Any]], from_item: str, to_item: str, production_line: str | None = None
) -> tuple[int, str | None]:
	"""Changeover minutes for one transition plus its annotation.

	Returns `(0, NO_NORM_NOTE)` when no norm matches — URS-W3-007 AC-2 asks for exactly
	that: no inserted time and a visible note.
	"""
	norm = best_matching(norms, from_item, to_item, production_line)
	if norm is None:
		return 0, NO_NORM_NOTE
	return int(norm.get("changeover_min") or 0), None
