"""Hazmat vocabulary and pure formatting rules (W2-7 · URS-W2-023, URS-W2-024).

Hazmat is **white space** in all three legacy systems (dossier §6.3, ch. G "Hazmat: Absent"
×3): there is no Qcadoo/OFBiz/ERPNext-legacy behaviour to absorb and therefore no parity
contract. The vocabulary below is therefore designed from German chemical-industry
regulation, which is the only authority available:

* **UN numbers** — UN Recommendations on the Transport of Dangerous Goods / ADR: exactly
  four digits, rendered `UN NNNN`.
* **Lagerklassen (storage classes)** — TRGS 510 Anlage 1 (Technische Regeln für
  Gefahrstoffe, "Lagerung von Gefahrstoffen in ortsbeweglichen Behältern"). The closed set
  below is the regulation's class list; a value outside it is refused.
* **GHS/CLP** — Regulation (EC) 1272/2008: signal word (Gefahr/Achtung), pictogram codes
  GHS01…GHS09, hazard statements `H…`/`EUH…` and precautionary statements `P…`.
* **WGK** — Wassergefährdungsklasse per AwSV (1, 2, 3, nwg).

Everything here is a pure function over plain data (no database access), so the rules are
usable from the DocType controller, the view decorations and the fixture seeder alike;
messages are German-first via `frappe._()`. Site-facing behaviour — the profile DocType, the
batch gate, the warehouse/trace decorations — lives in the sibling modules.
"""

from __future__ import annotations

import re
from typing import Any

from frappe import _

#: TRGS 510 Anlage 1 — Lagerklasse → German designation. Order is the regulation's order and
#: is also the Select field's option order.
STORAGE_CLASSES: dict[str, str] = {
	"1": "Explosive Stoffe",
	"2A": "Gase (verdichtet, verflüssigt, unter Druck gelöst)",
	"2B": "Aerosolpackungen und Feuerzeuge",
	"3": "Entzündbare Flüssigkeiten",
	"4.1A": "Sonstige explosionsgefährliche Stoffe",
	"4.1B": "Entzündbare feste Stoffe",
	"4.2": "Selbstentzündliche (pyrophore) Stoffe",
	"4.3": "Stoffe, die mit Wasser entzündbare Gase bilden",
	"5.1A": "Stark oxidierend wirkende Stoffe",
	"5.1B": "Oxidierend wirkende Stoffe",
	"5.1C": "Ammoniumnitrat und ammoniumnitrathaltige Zubereitungen",
	"5.2": "Organische Peroxide und selbstzersetzliche Stoffe",
	"6.1A": "Brennbare, akut toxische Stoffe (Kat. 1 und 2)",
	"6.1B": "Nicht brennbare, akut toxische Stoffe (Kat. 1 und 2)",
	"6.1C": "Brennbare, akut toxische Stoffe (Kat. 3) und chronisch wirkende Stoffe",
	"6.1D": "Nicht brennbare, akut toxische Stoffe (Kat. 3) und chronisch wirkende Stoffe",
	"6.2": "Ansteckungsgefährliche Stoffe",
	"7": "Radioaktive Stoffe",
	"8A": "Brennbare korrosive Stoffe",
	"8B": "Nicht brennbare korrosive Stoffe",
	"10": "Brennbare Flüssigkeiten (nicht Lagerklasse 3)",
	"11": "Brennbare Feststoffe",
	"12": "Nicht brennbare Flüssigkeiten",
	"13": "Nicht brennbare Feststoffe",
}

#: Storage classes whose hazard is acute (explosive, flammable, oxidising, acutely toxic,
#: radioactive). They carry the red hazmat signal; see `signal_for_storage_class`.
ACUTE_STORAGE_CLASSES: frozenset[str] = frozenset(
	{
		"1",
		"2A",
		"2B",
		"3",
		"4.1A",
		"4.1B",
		"4.2",
		"4.3",
		"5.1A",
		"5.1B",
		"5.1C",
		"5.2",
		"6.1A",
		"6.1B",
		"6.2",
		"7",
	}
)

#: Chronically toxic and corrosive classes — hazardous, but not an acute stop signal.
ADVISORY_STORAGE_CLASSES: frozenset[str] = frozenset({"6.1C", "6.1D", "8A", "8B"})

#: Regulation (EC) 1272/2008 Anhang V — pictogram code → German designation.
GHS_PICTOGRAMS: dict[str, str] = {
	"GHS01": "Explodierende Bombe",
	"GHS02": "Flamme",
	"GHS03": "Flamme über einem Kreis",
	"GHS04": "Gasflasche",
	"GHS05": "Ätzwirkung",
	"GHS06": "Totenkopf mit gekreuzten Gebeinen",
	"GHS07": "Ausrufezeichen",
	"GHS08": "Gesundheitsgefahr",
	"GHS09": "Umwelt",
}

SIGNAL_WORD_DANGER = "Gefahr"
SIGNAL_WORD_WARNING = "Achtung"
SIGNAL_WORDS: tuple[str, ...] = (SIGNAL_WORD_DANGER, SIGNAL_WORD_WARNING)

#: Wassergefährdungsklasse (AwSV) — `nwg` = nicht wassergefährdend.
WATER_HAZARD_CLASSES: tuple[str, ...] = ("1", "2", "3", "nwg")

STATEMENT_HAZARD = "H"
STATEMENT_PRECAUTIONARY = "P"

#: Statement-code shapes: `H224`, `EUH014` (hazard) and `P210` (precautionary).
HAZARD_CODE_PATTERN = re.compile(r"^(?:H\d{3}[A-Za-z]*|EUH\d{3}[A-Za-z]*)$")
PRECAUTIONARY_CODE_PATTERN = re.compile(r"^P\d{3}(?:\+P\d{3})*$")

UN_NUMBER_PATTERN = re.compile(r"^UN\s?(\d{4})$", re.IGNORECASE)

#: Design-skill signal tokens for the hazmat chip (icon + label + colour, never colour
#: alone — `rheinwerk-mes-design-SKILL.md` component rules).
SIGNAL_RED = {"tone": "red", "token": "--rw-signal-red", "icon": "alert-octagon"}
SIGNAL_AMBER = {"tone": "amber", "token": "--rw-signal-amber", "icon": "alert-triangle"}
SIGNAL_BLUE = {"tone": "blue", "token": "--rw-signal-blue", "icon": "info"}


class HazmatDataError(ValueError):
	"""A hazmat attribute violates its regulatory shape. Raised German-first."""


def normalise_un_number(value: str | None) -> str:
	"""`un 1866` / `UN1866` / `1866` → canonical `UN 1866`; refuse anything else.

	ADR/UN numbers are exactly four digits. The canonical rendering carries the `UN`
	prefix, so the identifier reads the same on screen, in the SDS and on a W3 label.
	"""
	raw = (value or "").strip()
	if not raw:
		raise HazmatDataError(_("Die UN-Nummer fehlt."))
	digits = raw if raw.isdigit() else ""
	if not digits:
		match = UN_NUMBER_PATTERN.match(raw)
		if not match:
			raise HazmatDataError(
				_("Ungültige UN-Nummer {0}. Erwartet werden vier Ziffern, z. B. UN 1866.").format(raw)
			)
		digits = match.group(1)
	if len(digits) != 4:
		raise HazmatDataError(
			_("Ungültige UN-Nummer {0}. Erwartet werden vier Ziffern, z. B. UN 1866.").format(raw)
		)
	return f"UN {digits}"


def validate_storage_class(value: str | None) -> str:
	"""Refuse a Lagerklasse outside the TRGS 510 class list."""
	raw = (value or "").strip().upper()
	if not raw:
		raise HazmatDataError(_("Die Lagerklasse fehlt."))
	if raw not in STORAGE_CLASSES:
		raise HazmatDataError(
			_("Unbekannte Lagerklasse {0}. Zulässig sind die Lagerklassen nach TRGS 510: {1}.").format(
				raw, ", ".join(STORAGE_CLASSES)
			)
		)
	return raw


def validate_statement_code(code: str | None, statement_type: str) -> str:
	"""Refuse an H-/EUH-/P-code that does not match its CLP shape."""
	raw = (code or "").strip().upper().replace(" ", "")
	if not raw:
		raise HazmatDataError(_("Der Code des Hinweises fehlt."))
	pattern = HAZARD_CODE_PATTERN if statement_type == STATEMENT_HAZARD else PRECAUTIONARY_CODE_PATTERN
	if not pattern.match(raw):
		raise HazmatDataError(
			_(
				"Ungültiger Code {0}. Gefahrenhinweise lauten H224 oder EUH014, Sicherheitshinweise P210."
			).format(raw)
		)
	return raw


def storage_class_label(storage_class: str) -> str:
	"""`3` → `Lagerklasse 3 — Entzündbare Flüssigkeiten` (German-first, never a bare code)."""
	designation = STORAGE_CLASSES.get(storage_class, "")
	if not designation:
		return _("Lagerklasse {0}").format(storage_class)
	return _("Lagerklasse {0} — {1}").format(storage_class, _(designation))


def signal_for_storage_class(storage_class: str) -> dict[str, str]:
	"""Signal tokens for a Lagerklasse: acute → red, toxic/corrosive → amber, else blue."""
	if storage_class in ACUTE_STORAGE_CLASSES:
		return dict(SIGNAL_RED)
	if storage_class in ADVISORY_STORAGE_CLASSES:
		return dict(SIGNAL_AMBER)
	return dict(SIGNAL_BLUE)


def hazmat_chip(profile: dict[str, Any] | None) -> dict[str, Any] | None:
	"""The hazmat chip every W2 surface renders (URS-W2-024).

	`None` for non-hazardous material — the chip is *absent*, never an empty placeholder.
	Otherwise a status-pill-shaped dict: UN number and Lagerklasse are both carried as data
	(`un_number`, `storage_class`) *and* in the label, so a stock table can column them and
	the Trace Ribbon can chip them from the same object.
	"""
	if not profile:
		return None
	un_number = profile.get("un_number") or ""
	storage_class = profile.get("storage_class") or ""
	label_parts = [
		part for part in (un_number, storage_class_label(storage_class) if storage_class else "") if part
	]
	return {
		"profile": profile.get("name"),
		"un_number": un_number,
		"storage_class": storage_class,
		"storage_class_label": storage_class_label(storage_class) if storage_class else "",
		"water_hazard_class": profile.get("water_hazard_class") or "",
		"signal_word": profile.get("signal_word") or "",
		"sds_reference": profile.get("sds_reference") or "",
		"label": " · ".join(label_parts),
		"kind": "hazmat",
		**signal_for_storage_class(storage_class),
	}
