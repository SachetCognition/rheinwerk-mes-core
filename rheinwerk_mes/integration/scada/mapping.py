"""Tag → work-centre mapping resolution (W3-5 · URS-W3-016).

The mapping is technologist-maintained master data (`OPC UA Tag Mapping`, Desk list view).
A work centre is addressed the way the plant names it and the way CDM-08 models it — as the
composite code `<Produktionslinie>/<Arbeitsplatz>`, e.g. `LINE-1/MIX-01` — held in a Data
field rather than a Link, because the acceptance criterion is a refusal that *names the
invalid code* (URS-W3-016 AC-2) and Frappe validates Link targets before the controller's
`validate` ever runs, which would swallow the code in a generic link error. The resolved
`Production Line` and `Workstation` are written to read-only Link fields, so referential
integrity is still visible on the form and in reports.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.integration.scada.contracts import WORK_CENTRE_CODE_SEPARATOR

MAPPING_DOCTYPE = "OPC UA Tag Mapping"


class WorkCentreResolution(frappe.ValidationError):
	"""Raised when a work-centre code does not resolve to an existing work centre."""


def work_centre_code(production_line: str | None, workstation: str) -> str:
	"""The composite code of a work centre, as the plant and CDM-08 name it."""
	if not production_line:
		return workstation
	return f"{production_line}{WORK_CENTRE_CODE_SEPARATOR}{workstation}"


def _refuse(code: str, reason: str) -> None:
	frappe.throw(
		_("Arbeitsplatz {0} ist nicht bekannt: {1}").format(code, reason),
		WorkCentreResolution,
		title=_("Zuordnung abgelehnt"),
	)


def resolve_work_centre(code: str) -> dict[str, str]:
	"""Split and validate a work-centre code; refuses naming the invalid code (AC-2)."""
	raw = (code or "").strip()
	if not raw:
		_refuse(_("(leer)"), _("kein Arbeitsplatzschlüssel angegeben"))
	parts = [part.strip() for part in raw.split(WORK_CENTRE_CODE_SEPARATOR)]
	if len(parts) != 2 or not all(parts):
		_refuse(raw, _("erwartet wird Linie/Arbeitsplatz, z. B. LINE-1/MIX-01"))
	line, workstation = parts

	if not frappe.db.exists("Production Line", line):
		_refuse(raw, _("Produktionslinie {0} existiert nicht").format(line))
	if not frappe.db.exists("Workstation", workstation):
		_refuse(raw, _("Arbeitsplatz {0} existiert nicht").format(workstation))

	assigned_line = (
		frappe.db.get_value("Workstation", workstation, "production_line")
		if frappe.get_meta("Workstation").has_field("production_line")
		else None
	)
	if assigned_line and assigned_line != line:
		_refuse(raw, _("Arbeitsplatz {0} gehört zu Linie {1}").format(workstation, assigned_line))

	return {"production_line": line, "work_centre": workstation, "work_centre_code": raw}


def mapping_for_tag(tag_address: str) -> dict[str, Any] | None:
	"""The active mapping of one OPC-UA node address, or `None` when the tag is unmapped."""
	rows = frappe.get_all(
		MAPPING_DOCTYPE,
		filters={"tag_address": tag_address, "enabled": 1},
		fields=[
			"name",
			"tag_address",
			"event_type",
			"work_centre_code",
			"work_centre",
			"production_line",
			"operation",
			"uom",
		],
		limit=1,
	)
	return rows[0] if rows else None


def mappings_of_work_centre(code: str) -> list[dict[str, Any]]:
	"""Every active mapping of one work centre — the adapter's subscription list."""
	return frappe.get_all(
		MAPPING_DOCTYPE,
		filters={"work_centre_code": code, "enabled": 1},
		fields=["name", "tag_address", "event_type", "operation", "uom"],
		order_by="tag_address asc",
	)


def upsert_mapping(
	*,
	tag_address: str,
	work_centre_code: str,
	event_type: str,
	operation: str | None = None,
	uom: str = "Kg",
	description: str | None = None,
) -> Any:
	"""Create or update one mapping from code — the seeder's and installer's entry point."""
	name = frappe.db.get_value(MAPPING_DOCTYPE, {"tag_address": tag_address}, "name")
	doc = frappe.get_doc(MAPPING_DOCTYPE, name) if name else frappe.new_doc(MAPPING_DOCTYPE)
	doc.update(
		{
			"tag_address": tag_address,
			"work_centre_code": work_centre_code,
			"event_type": event_type,
			"operation": operation,
			"uom": uom,
			"description": description,
			"enabled": 1,
		}
	)
	doc.save(ignore_permissions=True)
	return doc
