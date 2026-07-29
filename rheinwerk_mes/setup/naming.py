"""Estate-wide naming/numbering scheme (URS-W0-014, W0-8).

Decision and rationale: `docs/adr/ADR-011-naming-numbering.md`. Platform-native
Frappe naming series replace the Qcadoo DB-trigger sequences; legacy
trigger-generated numbers survive in the `legacy_refs` mapping instead of in the
primary key.

`SERIES` is the single registry every wave reads, so W1/W2 apply the batch and
handling-unit series when those entities land rather than inventing their own.
A series is applied only once its DocType and all fields it interpolates exist,
which keeps W0 out of the W2 batch/handling-unit footprint.
"""

from __future__ import annotations

import frappe
from frappe.model.naming import parse_naming_series

from rheinwerk_mes.setup.property_setters import set_property

WORK_ORDER_SERIES = "PO-.YYYY.-.####."
BATCH_SERIES = "BATCH-.{plant}.-.####."
HANDLING_UNIT_SERIES = "HU-.####."

SERIES: dict[str, str] = {
	"Work Order": WORK_ORDER_SERIES,
	"Batch": BATCH_SERIES,
	"Handling Unit": HANDLING_UNIT_SERIES,
}


def series_dependencies(series: str) -> list[str]:
	"""Fieldnames a series interpolates, e.g. `plant` in `BATCH-.{plant}.-.####.`."""
	return [part[1:-1] for part in series.split(".") if part.startswith("{") and part.endswith("}")]


def is_applicable(doctype: str, series: str) -> bool:
	"""True when the DocType exists and carries every field the series needs."""
	if not frappe.db.exists("DocType", doctype):
		return False
	meta = frappe.get_meta(doctype)
	if not meta.get_field("naming_series"):
		return False
	return all(meta.get_field(fieldname) for fieldname in series_dependencies(series))


def preview(series: str, values: dict[str, str], counter: int = 1) -> str:
	"""Render a series without touching the DB counter (used by the naming tests)."""

	def fake_counter(_prefix: str, digits: int) -> str:
		return str(counter).zfill(digits)

	return parse_naming_series(series, doc=frappe._dict(values), number_generator=fake_counter)


def install_naming_series() -> list[str]:
	"""Point every applicable anchor at its canonical series; safe to re-run."""
	applied = []
	for doctype, series in SERIES.items():
		if not is_applicable(doctype, series):
			continue
		options = frappe.get_meta(doctype).get_field("naming_series").options or ""
		choices = [line for line in options.splitlines() if line.strip()]
		if series in choices:
			choices.remove(series)
		choices.insert(0, series)
		set_property(doctype, "naming_series", "options", "\n".join(choices), "Text")
		set_property(doctype, "naming_series", "default", series, "Text")
		applied.append(doctype)
	frappe.clear_cache()
	return applied
