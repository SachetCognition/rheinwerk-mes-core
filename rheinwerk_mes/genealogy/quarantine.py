"""Quarantine storage locations (W2-3 · URS-W2-012).

A `Storage Location` (the W1 tree) can be flagged as a quarantine location through the
`is_quarantine_location` Custom Field created by `rheinwerk_mes.setup.w2_genealogy`. Two
behaviours follow:

* **Putaway proposal** — stock of a Quarantined batch is proposed into a quarantine
  location of the receiving warehouse (AC-1).
* **Movement gate** — moving stock *out of* a quarantine location is reserved to the
  quality inspector and the warehouse clerk, and a still-Quarantined batch may not leave
  at all (AC-2): the operator role is refused, the clerk posts once the batch is Released.

Legacy baseline (semantics only, never ported) in `SachetCognition/Chem_mes@master`:
`mes-plugins/mes-plugins-material-flow-resources/src/main/resources/.../model/
storageLocation.xml:37-54` — Qcadoo carries per-location flags on the storage-location
model; the quarantine flag and its role gate are the Rheinwerk extension (ADR-005/CDM-03).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from rheinwerk_mes.genealogy import links, qa_state

QUARANTINE_FIELD = "is_quarantine_location"

#: Roles allowed to move stock out of a quarantine location (URS-W2-012 AC-2).
ALLOWED_EXIT_ROLES: tuple[str, ...] = ("Quality Manager", "Rheinwerk Warehouse Clerk", "System Manager")

RULE_QUARANTINE_EXIT = "quarantine_location_exit"


def is_quarantine_location(storage_location: str | None) -> bool:
	if not storage_location:
		return False
	return bool(frappe.db.get_value("Storage Location", storage_location, QUARANTINE_FIELD))


def quarantine_locations(warehouse: str) -> list[str]:
	"""Quarantine-flagged locations of `warehouse`, alphabetical."""
	return frappe.get_all(
		"Storage Location",
		filters={"warehouse": warehouse, QUARANTINE_FIELD: 1, "is_group": 0},
		pluck="name",
		order_by="name asc",
	)


def putaway_proposal(batch: str, warehouse: str) -> str | None:
	"""Storage location proposed for `batch` in `warehouse` (URS-W2-012 AC-1).

	A Quarantined batch is directed to a quarantine location; anything else keeps the
	batch's own location, so the proposal never moves released stock into quarantine.
	"""
	if qa_state.current_state(batch) == qa_state.QUARANTINED:
		candidates = quarantine_locations(warehouse)
		if candidates:
			return candidates[0]
	return frappe.db.get_value("Batch", batch, "storage_location")


def enforce_quarantine_exit(doc: Any, method: str | None = None) -> None:
	"""`Stock Entry.validate` — gate movements out of a quarantine location (AC-2)."""
	roles = set(frappe.get_roles())
	for row in doc.get("items") or []:
		if not row.get("s_warehouse") or not is_quarantine_location(row.get("storage_location")):
			continue
		for batch in links.row_batches(row):
			state = qa_state.current_state(batch)
			if state == qa_state.QUARANTINED:
				frappe.throw(
					_(
						"<b>Regel:</b> Bestand in Quarantäne darf den Quarantäneplatz nicht verlassen [{0}]."
						"<br><b>Datensatz:</b> Charge {1}, Lagerplatz {2}"
						"<br><b>Behebung:</b> QA-Freigabe der Charge abwarten."
					).format(RULE_QUARANTINE_EXIT, batch, row.storage_location),
					title=_("Buchung abgelehnt: Quarantäneplatz"),
				)
			if not roles.intersection(ALLOWED_EXIT_ROLES):
				frappe.throw(
					_(
						"<b>Regel:</b> Auslagerungen aus einem Quarantäneplatz sind den Rollen {0} vorbehalten [{1}]."
						"<br><b>Datensatz:</b> Charge {2}, Lagerplatz {3}"
						"<br><b>Behebung:</b> Buchung durch Qualitätsprüfer oder Lagerist durchführen lassen."
					).format(
						", ".join(ALLOWED_EXIT_ROLES[:2]), RULE_QUARANTINE_EXIT, batch, row.storage_location
					),
					frappe.PermissionError,
					title=_("Buchung abgelehnt: Quarantäneplatz"),
				)
