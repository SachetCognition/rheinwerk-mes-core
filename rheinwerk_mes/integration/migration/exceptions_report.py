"""Exceptions report for records a source cannot map (URS-W0-010 AC-2).

An unmappable record is never imported with a defaulted value: it appears here, German
first, with its source entity, source identifier and reason, so the plant data owner can
decide the mapping before the next run.
"""

from __future__ import annotations

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract

REASON_LABELS = {"unmappable_uom": "Mengeneinheit ohne kanonische Entsprechung"}

HEADER = ("Quell-Entität", "Quell-ID", "Ziel-Entität", "Grund", "Detail")


def reason_label(reason: str) -> str:
	return REASON_LABELS.get(reason, reason)


def to_markdown(extract: CanonicalExtract) -> str:
	"""Render the extract's exceptions as a markdown report."""
	lines = [
		f"# Ausnahmenbericht Stammdatenmigration — {extract.source_system}",
		"",
		f"Nicht importierte Datensätze: {len(extract.exceptions)}",
		"",
	]
	if not extract.exceptions:
		lines.append("Keine Ausnahmen — alle Quelldatensätze konnten abgebildet werden.")
		return "\n".join(lines) + "\n"

	lines += [
		"| " + " | ".join(HEADER) + " |",
		"|" + "|".join(["---"] * len(HEADER)) + "|",
	]
	for exception in extract.sorted_exceptions():
		lines.append(
			"| "
			+ " | ".join(
				(
					exception.source_entity,
					exception.source_identifier,
					exception.entity,
					reason_label(exception.reason),
					exception.detail,
				)
			)
			+ " |"
		)
	return "\n".join(lines) + "\n"
