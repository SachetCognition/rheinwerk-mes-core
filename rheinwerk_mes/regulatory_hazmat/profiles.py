"""Profile resolution and the batch-level hazmat gate (W2-7 · URS-W2-023).

The hazmat profile is master data on the **Item**; a Batch may override it for repacked or
re-drummed goods (URS-W2-023 AC-1), so every surface resolves the *effective* profile
through `effective_profile()` and nowhere else. This is the API the sibling W2 packages and
W3-6 (shipping/label boundary) consume — see `docs/design/W2-hazmat.md`.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import formatdate

from rheinwerk_mes.regulatory_hazmat import contracts

PROFILE_DOCTYPE = "Hazmat Profile"

#: Custom Fields the W2-7 installer owns (`rheinwerk_mes/setup/w2_hazmat.py`).
ITEM_PROFILE_FIELD = "rw_hazmat_profile"
ITEM_MANDATORY_FIELD = "rw_hazmat_mandatory"
BATCH_PROFILE_FIELD = "rw_hazmat_profile"
BATCH_UN_NUMBER_FIELD = "rw_hazmat_un_number"
BATCH_STORAGE_CLASS_FIELD = "rw_hazmat_storage_class"

#: Profile fields every consumer needs; read in one go so a stock view is one query per row.
PROFILE_FIELDS: tuple[str, ...] = (
	"name",
	"profile_name",
	"un_number",
	"proper_shipping_name",
	"storage_class",
	"storage_class_designation",
	# W3-6: ADR transport data — the shipping boundary reads the same profile (URS-W3-018).
	"adr_class",
	"adr_class_designation",
	"adr_packing_group",
	"adr_tunnel_code",
	"adr_label_numbers",
	"adr_dispatch_ready",
	"water_hazard_class",
	"signal_word",
	"sds_reference",
	"sds_version",
	"sds_revision_date",
	"revision",
)


def profile(name: str | None) -> dict[str, Any] | None:
	"""Profile as a plain dict (German-rendered SDS date), or `None`."""
	if not name:
		return None
	values = frappe.db.get_value(PROFILE_DOCTYPE, name, list(PROFILE_FIELDS), as_dict=True)
	if not values:
		return None
	if values.get("sds_revision_date"):
		values["sds_revision_date"] = formatdate(values["sds_revision_date"], "dd.MM.yyyy")
	return dict(values)


def item_profile_name(item: str | None) -> str | None:
	if not item:
		return None
	return frappe.db.get_value("Item", item, ITEM_PROFILE_FIELD)


def effective_profile_name(batch: str | None = None, item: str | None = None) -> str | None:
	"""The batch override if present, else the item's profile (URS-W2-023 AC-1)."""
	if batch:
		values = frappe.db.get_value("Batch", batch, [BATCH_PROFILE_FIELD, "item"], as_dict=True)
		if values:
			if values.get(BATCH_PROFILE_FIELD):
				return values[BATCH_PROFILE_FIELD]
			item = item or values.get("item")
	return item_profile_name(item)


def effective_profile(batch: str | None = None, item: str | None = None) -> dict[str, Any] | None:
	"""Resolved hazmat profile of a batch (or bare item); `None` for non-hazardous stock."""
	return profile(effective_profile_name(batch=batch, item=item))


def batch_chip(batch: str) -> dict[str, Any] | None:
	"""Hazmat chip for a batch — the object warehouse and trace surfaces render (URS-W2-024)."""
	return contracts.hazmat_chip(effective_profile(batch=batch))


def item_chip(item: str) -> dict[str, Any] | None:
	"""Hazmat chip for an item, for surfaces that render before a batch exists."""
	return contracts.hazmat_chip(effective_profile(item=item))


def is_hazmat_mandatory(item: str | None) -> bool:
	if not item:
		return False
	return bool(frappe.db.get_value("Item", item, ITEM_MANDATORY_FIELD))


def enforce_hazmat_profile(doc, method: str | None = None) -> None:
	"""Batch `validate` hook: a hazmat-mandatory item may not carry an unprofiled batch.

	URS-W2-023 AC-2 — creation is refused *naming the missing profile* (design skill: a gate
	refusal names rule, record and resolution). Registered additively in `hooks.py`
	(`doc_events["Batch"]["validate"]`), so no sibling module changes.
	"""
	item = doc.get("item")
	if not is_hazmat_mandatory(item):
		return
	if effective_profile_name(item=item) or doc.get(BATCH_PROFILE_FIELD):
		return
	frappe.throw(
		_(
			"Regel: Für Artikel {0} ist ein Gefahrstoffprofil vorgeschrieben. "
			"Datensatz: Charge {1}. Abhilfe: Gefahrstoffprofil am Artikel hinterlegen "
			"oder an der Charge überschreiben (Feld „Gefahrstoffprofil“)."
		).format(item, doc.get("batch_id") or doc.get("name") or _("(neu)")),
		title=_("Gefahrstoffprofil fehlt"),
	)


def sync_batch_hazmat_fields(doc, method: str | None = None) -> None:
	"""Batch `validate` hook: mirror UN number and Lagerklasse onto the batch.

	The two read-only mirror fields are what makes hazmat a *column* in any Batch-backed
	list or stock view without a client-side join (URS-W2-024, design skill "nothing hides
	on desktop"). The profile link stays the single source of truth — the mirrors are
	refreshed on every save.
	"""
	# The document in hand may not be saved yet, so the override is read off the document
	# rather than through `effective_profile(batch=...)`.
	profile_name = doc.get(BATCH_PROFILE_FIELD) or item_profile_name(doc.get("item"))
	resolved = profile(profile_name)
	doc.set(BATCH_UN_NUMBER_FIELD, (resolved or {}).get("un_number") or None)
	doc.set(BATCH_STORAGE_CLASS_FIELD, (resolved or {}).get("storage_class") or None)


def refresh_item_batches(doc, method: str | None = None) -> None:
	"""Item `validate` hook counterpart: keep existing batches' mirrors in step.

	Called after an Item's hazmat profile changed; only the mirror fields are written (no
	Batch `validate` run, so no disposition side effects).
	"""
	before = doc.get_doc_before_save()
	if not before or before.get(ITEM_PROFILE_FIELD) == doc.get(ITEM_PROFILE_FIELD):
		return
	resolved = profile(doc.get(ITEM_PROFILE_FIELD)) or {}
	batches = frappe.get_all(
		"Batch",
		filters={"item": doc.name, BATCH_PROFILE_FIELD: ("in", ("", None))},
		pluck="name",
		limit_page_length=0,
	)
	for batch in batches:
		frappe.db.set_value(
			"Batch",
			batch,
			{
				BATCH_UN_NUMBER_FIELD: resolved.get("un_number"),
				BATCH_STORAGE_CLASS_FIELD: resolved.get("storage_class"),
			},
			update_modified=False,
		)
