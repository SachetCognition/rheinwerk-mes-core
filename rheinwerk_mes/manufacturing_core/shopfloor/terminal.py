"""Desk/Terminal density modes for the W1 screens (URS-W1-035, URS-W1-032).

The two density modes are a first-class token, not a hidden preference (design skill
§ "Density modes"): Terminal mode enlarges, it never hides — both modes expose the same
fields. The tokens live here so the server, the page assets and the conformance tests all
read one definition; `rheinwerk_mes/public/css/shopfloor.css` mirrors them as CSS
variables and `shopfloor.js` switches the mode in one tap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from frappe import _

DESK = "Desk"
TERMINAL = "Terminal"


def _lazy(message: str) -> str:
	"""Mark a message id that is translated when it is read, not when it is defined."""
	return message


@dataclass(frozen=True)
class DensityMode:
	"""Measurable tokens of one density mode."""

	name: str
	base_font_px: int
	row_height_px: int
	min_target_px: int
	pill_font_px: int


MODES: dict[str, DensityMode] = {
	DESK: DensityMode(name=DESK, base_font_px=14, row_height_px=32, min_target_px=32, pill_font_px=12),
	TERMINAL: DensityMode(
		name=TERMINAL, base_font_px=18, row_height_px=56, min_target_px=48, pill_font_px=16
	),
}

#: Fields every W1 shop-floor screen shows in *both* modes (terminal never hides data).
SHARED_FIELDS: tuple[str, ...] = (
	"work_order",
	"operation",
	"workstation",
	"exec_state",
	"job_card",
	"job_status",
	"for_quantity",
	"total_completed_qty",
	"planned_start_date",
)

#: Icon per state so a pill is never colour-only (design skill § "Component rules").
STATE_ICONS: dict[str, str] = {
	"Pending": "\u23f1",
	"Accepted": "\u2713",
	"In Progress": "\u25b6",
	"Completed": "\u2714",
	"Interrupted": "\u23f8",
	"Abandoned": "\u23f9",
	"Declined": "\u2715",
	"Open": "\u23f1",
	"Work In Progress": "\u25b6",
	"On Hold": "\u23f8",
	"Material Transferred": "\u2192",
	"Submitted": "\u2714",
	"Cancelled": "\u2715",
}

#: Complete keyboard path published per screen; `?` opens the sheet. Labels are message
#: ids translated on read, never at import time.
SHORTCUTS: tuple[tuple[str, str], ...] = (
	("Enter", _lazy("Aktion bestätigen")),
	("Esc", _lazy("Aktion abbrechen")),
	("↑ / ↓", _lazy("Auftragszeile wechseln")),
	("F2", _lazy("Dichtemodus umschalten")),
	("?", _lazy("Tastaturkürzel anzeigen")),
)


def resolve_mode(station_profile: str | None = None) -> str:
	"""Auto-select the mode from the station profile; Desk is the default."""
	return TERMINAL if (station_profile or "").strip().lower() == "terminal" else DESK


def mode_tokens(mode: str) -> dict[str, object]:
	"""Tokens of `mode` plus the shared field list and shortcut sheet."""
	density = MODES.get(mode) or MODES[DESK]
	return {
		**asdict(density),
		"fields": list(SHARED_FIELDS),
		"shortcuts": [{"keys": keys, "action": _(action)} for keys, action in SHORTCUTS],
	}


def state_pill(state: str | None) -> dict[str, str]:
	"""The one status-pill payload used everywhere: icon + label (+ colour in CSS)."""
	label = state or "Pending"
	return {"state": label, "label": _(label), "icon": STATE_ICONS.get(label, "\u25cf")}
