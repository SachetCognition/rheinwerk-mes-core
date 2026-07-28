"""W1-7 installer — shop-floor site artefacts (URS-W1-022, URS-W1-026…028, URS-W1-035).

Everything the operator journey needs on a site is created here from committed code and
idempotently: the station-profile Custom Field driving Desk/Terminal auto-selection, the
legacy-bridge feature flag with its hover hints, and the workstation scan codes. The
anchor `Job Card` and `Workstation` DocTypes are never forked.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from the `patches.txt`
entry (existing sites).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.manufacturing_core.shopfloor import legacy_bridge, terminal

MANUFACTURING_CORE = "Manufacturing Core"


def custom_field_definitions() -> dict[str, list[dict]]:
	"""Station profile on the anchor Workstation; scan hint on the anchor Job Card."""
	return {
		"Workstation": [
			{
				"fieldname": "station_profile",
				"label": _("Stationsprofil"),
				"fieldtype": "Select",
				"options": "\n".join((terminal.DESK, terminal.TERMINAL)),
				"default": terminal.TERMINAL,
				"insert_after": "workstation_name",
				"description": _(
					"Bestimmt den Dichtemodus der Shopfloor-Oberfläche "
					"(Terminal: 18px Basisschrift, 48px Bedienflächen)."
				),
				"module": MANUFACTURING_CORE,
			}
		],
		"Job Card": [
			{
				"fieldname": "rw_scan_code",
				"label": _("Scan-Code"),
				"fieldtype": "Data",
				"insert_after": "operation",
				"read_only": 1,
				"allow_on_submit": 1,
				"description": _("Barcode, der diesen Arbeitsgang am Terminal identifiziert."),
				"module": MANUFACTURING_CORE,
			}
		],
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def install_legacy_bridge(enabled: bool = True) -> int:
	"""Switch the migration-programme hover affordance on and apply it (URS-W1-022)."""
	frappe.defaults.set_global_default(legacy_bridge.FLAG_KEY, "1" if enabled else "0")
	return legacy_bridge.apply_hints()


def backfill_scan_codes() -> int:
	"""Give existing job cards their scan code (the card name is the printed barcode)."""
	names = frappe.get_all(
		"Job Card", filters={"rw_scan_code": ("in", ("", None))}, pluck="name", limit_page_length=0
	)
	for name in names:
		frappe.db.set_value("Job Card", name, "rw_scan_code", name, update_modified=False)
	return len(names)


def set_job_card_scan_code(doc, method: str | None = None) -> None:
	"""`Job Card.validate` hook — the card's own name is its barcode."""
	if doc.meta.has_field("rw_scan_code") and not doc.get("rw_scan_code") and not doc.get("__islocal"):
		doc.rw_scan_code = doc.name


def setup_w1_shopfloor() -> dict[str, object]:
	"""Install every W1-7 site artefact; safe to re-run."""
	install_custom_fields()
	summary: dict[str, object] = {"legacy_hints": install_legacy_bridge(True)}
	summary["scan_codes"] = backfill_scan_codes()
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_shopfloor()
