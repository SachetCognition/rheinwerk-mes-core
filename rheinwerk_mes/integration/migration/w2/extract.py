"""Offline extraction + dual-model merge for the W2 migration pilot (URS-W2-030…032).

Each source function reads one committed pilot fixture and returns a `W2Extract`. No Frappe
site is touched, so the merge / fold / mapping decisions are unit-testable and deterministic.

Legacy shapes re-expressed (semantics only, never ported) from:
* `SachetCognition/Chem_mes@master` — `BatchState.java:31-44` (TRACKED/BLOCKED),
  `ResourceFields.java` (`batch`, `expirationDate`, `blockedForQualityControl`,
  `qualityRating`), `TrackingRecordFields.java` (used/produced trees);
* `SachetCognition/VM_ofbiz-framework@trunk` — `WorkEffortInventoryAssign` /
  `WorkEffortInventoryProduced` (`lotId` presence decides the trace boundary).

Field-level target mapping is authoritative in `docs/canonical-model/README.md` (CDM-01, CDM-07).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rheinwerk_mes.integration.migration.w2.model import (
	BLOCKED,
	CONSUMED,
	PRODUCED,
	QUARANTINED,
	RELEASED,
	LegacyRef,
	StagedBatch,
	StagedLink,
	W2Extract,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "w2"

DEFAULT_FIXTURES: dict[str, str] = {
	"qcadoo": "plant-a-qcadoo.json",
	"ofbiz": "plant-b-ofbiz.json",
	"erpnext": "plant-c-erpnext.json",
}

SOURCES: tuple[str, ...] = ("qcadoo", "ofbiz", "erpnext")

# BatchState.java:31-44 — the two open-batch dispositions this migration carries.
_QCADOO_TRACKED = "tracked"
_QCADOO_BLOCKED = "blocked"


def _load(fixture: str | Path) -> dict[str, Any]:
	return json.loads(Path(fixture).read_text(encoding="utf-8"))


def _fixture_path(source: str, fixture: str | Path | None) -> Path:
	if fixture is not None:
		return Path(fixture)
	return FIXTURE_DIR / DEFAULT_FIXTURES[source]


def _de(iso_date: str | None) -> str | None:
	"""ISO `YYYY-MM-DD` → German `DD.MM.YYYY` for user-facing report/conflict strings."""
	if not iso_date:
		return None
	return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")


def _earliest_expiry(iso_dates: list[str]) -> tuple[str | None, list[str]]:
	"""Earliest expiry wins; return it plus the distinct set for conflict reporting."""
	present = sorted({date for date in iso_dates if date})
	if not present:
		return None, []
	return present[0], present


# --------------------------------------------------------------------------------------
# Qcadoo (Plant A) — dual-model merge + TrackingRecord fold + quality flags.
# --------------------------------------------------------------------------------------


def _qcadoo_state(genealogy_state: str | None) -> str:
	token = (genealogy_state or "").lower()
	if _QCADOO_BLOCKED in token:
		return _QCADOO_BLOCKED
	if _QCADOO_TRACKED in token:
		return _QCADOO_TRACKED
	return "none"


def extract_qcadoo(fixture: str | Path | None = None) -> W2Extract:
	data = _load(_fixture_path("qcadoo", fixture))
	genealogy = {row["number"]: row for row in data.get("genealogy_batches", ())}

	resources_by_batch: dict[str, list[dict[str, Any]]] = {}
	for resource in data.get("resources", ()):
		resources_by_batch.setdefault(resource["batch"], []).append(resource)

	batches: list[StagedBatch] = []
	conflicts: list[str] = []
	for batch_id in sorted(set(genealogy) | set(resources_by_batch)):
		gb = genealogy.get(batch_id)
		lots = resources_by_batch.get(batch_id, [])
		matched = gb is not None
		item = gb["product"] if gb else lots[0]["product"]

		expiry, distinct_expiries = _earliest_expiry([lot.get("expirationDate") for lot in lots])
		conflict = None
		if len(distinct_expiries) > 1:
			conflict = "{batch}: Ablaufdatum-Konflikt {options} — frühestes gewählt ({chosen})".format(
				batch=batch_id,
				options=" vs ".join(_de(date) or "—" for date in distinct_expiries),
				chosen=_de(expiry),
			)
			conflicts.append(conflict)

		blocked_for_qc = any(lot.get("blockedForQualityControl") for lot in lots)
		gb_state = _qcadoo_state(gb["state"] if gb else None)
		if blocked_for_qc:
			qa_state, legacy_state = QUARANTINED, "blocked_for_quality_control"
			origin = "Legacy-Qualitätskennzeichen: blockedForQualityControl (Qcadoo Resource)"
		elif gb_state == _QCADOO_BLOCKED:
			qa_state, legacy_state = BLOCKED, "blocked"
			origin = "Legacy-Status: BatchState BLOCKED (Qcadoo Batch)"
		else:
			qa_state, legacy_state = RELEASED, "tracked" if matched else "none"
			origin = None

		refs = []
		if matched:
			refs.append(LegacyRef("Qcadoo", "advancedgenealogy_batch", batch_id))
		if lots:
			refs.append(LegacyRef("Qcadoo", "materialflowresources_resource", batch_id))

		supplier = next((lot.get("supplierBatch") for lot in lots if lot.get("supplierBatch")), None)
		qty = sum(float(lot.get("quantity") or 0) for lot in lots) or None

		batches.append(
			StagedBatch(
				batch_id=batch_id,
				item=item,
				expiry_date=expiry,
				qa_state=qa_state,
				genealogy_incomplete=not matched,
				legacy_refs=tuple(refs),
				legacy_state=legacy_state,
				qty_original=qty,
				supplier_batch_no=supplier,
				qa_state_origin=origin,
				expiry_conflict=conflict,
			)
		)

	links, used_rows, produced_rows = _fold_trees(
		data.get("tracking_records", ()),
		batches={b.batch_id: b for b in batches},
		order_key="order",
	)

	return W2Extract(
		plant=data.get("plant", "A"),
		source="qcadoo",
		batches=tuple(batches),
		links=tuple(links),
		expiry_conflicts=tuple(conflicts),
		source_used_rows=used_rows,
		source_produced_rows=produced_rows,
	)


# --------------------------------------------------------------------------------------
# OFBiz (Plant B) — lots + WorkEffort inventory; lotId presence decides the trace boundary.
# --------------------------------------------------------------------------------------


def extract_ofbiz(fixture: str | Path | None = None) -> W2Extract:
	data = _load(_fixture_path("ofbiz", fixture))
	boundary = data.get("trace_boundary_date")

	# First pass over work efforts: which produced lots have an untraceable (no lotId) input.
	incomplete: set[str] = set()
	for effort in data.get("work_efforts", ()):
		produced_lot = effort["produced"]["lotId"]
		if any(not row.get("lotId") for row in effort.get("assigned", ())):
			incomplete.add(produced_lot)

	batches: list[StagedBatch] = []
	for lot in data.get("lots", ()):
		lot_id = lot["lotId"]
		is_incomplete = lot_id in incomplete
		batches.append(
			StagedBatch(
				batch_id=lot_id,
				item=lot["productId"],
				expiry_date=lot.get("expirationDate"),
				qa_state=RELEASED,
				genealogy_incomplete=is_incomplete,
				legacy_refs=(LegacyRef("OFBiz", "Lot", lot_id),),
				legacy_state="none",
				trace_boundary_date=boundary if is_incomplete else None,
				qty_original=float(lot.get("quantity") or 0) or None,
				supplier_batch_no=lot.get("supplierBatch"),
			)
		)

	links: list[StagedLink] = []
	used_rows = produced_rows = 0
	for effort in data.get("work_efforts", ()):
		produced = effort["produced"]
		produced_lot = produced["lotId"]
		produced_rows += 1
		links.append(
			StagedLink(
				produced_batch=produced_lot,
				direction=PRODUCED,
				batch=produced_lot,
				item=produced.get("productId"),
				qty=float(produced.get("quantity") or 0),
				uom=produced.get("uom"),
				legacy_order=effort.get("workEffortId"),
			)
		)
		for row in effort.get("assigned", ()):
			if not row.get("lotId"):
				# Untraceable consumption: no canonical batch to link, boundary already noted.
				continue
			used_rows += 1
			links.append(
				StagedLink(
					produced_batch=produced_lot,
					direction=CONSUMED,
					batch=row["lotId"],
					item=row.get("productId"),
					qty=float(row.get("quantity") or 0),
					uom=row.get("uom"),
					legacy_order=effort.get("workEffortId"),
				)
			)

	return W2Extract(
		plant=data.get("plant", "B"),
		source="ofbiz",
		batches=tuple(batches),
		links=tuple(links),
		trace_boundary_date=boundary,
		source_used_rows=used_rows,
		source_produced_rows=produced_rows,
		incomplete_boundary_batches=tuple(sorted(incomplete)),
	)


# --------------------------------------------------------------------------------------
# ERPNext legacy (Plant C) — anchor Batch + SLE-derived production history.
# --------------------------------------------------------------------------------------


def extract_erpnext(fixture: str | Path | None = None) -> W2Extract:
	data = _load(_fixture_path("erpnext", fixture))
	batches: list[StagedBatch] = []
	for row in data.get("batches", ()):
		disabled = bool(row.get("disabled"))
		batches.append(
			StagedBatch(
				batch_id=row["batch_no"],
				item=row["item"],
				expiry_date=row.get("expiry_date"),
				qa_state=BLOCKED if disabled else RELEASED,
				genealogy_incomplete=False,
				legacy_refs=(LegacyRef("ERPNext Legacy", "Batch", row["batch_no"]),),
				legacy_state="disabled" if disabled else "none",
				qty_original=float(row.get("quantity") or 0) or None,
				supplier_batch_no=row.get("supplier_batch"),
				qa_state_origin="Legacy-Status: Batch disabled (ERPNext)" if disabled else None,
			)
		)

	links, used_rows, produced_rows = _fold_trees(
		data.get("production_history", ()),
		batches={b.batch_id: b for b in batches},
		order_key="order",
	)

	return W2Extract(
		plant=data.get("plant", "C"),
		source="erpnext",
		batches=tuple(batches),
		links=tuple(links),
		source_used_rows=used_rows,
		source_produced_rows=produced_rows,
	)


def _fold_trees(
	records: tuple[dict[str, Any], ...],
	*,
	batches: dict[str, StagedBatch],
	order_key: str,
) -> tuple[list[StagedLink], int, int]:
	"""Fold TrackingRecord / production-history used trees onto their produced batch."""
	links: list[StagedLink] = []
	used_rows = produced_rows = 0
	for record in records:
		produced_batch = record["producedBatch"]
		produced_rows += 1
		staged = batches.get(produced_batch)
		links.append(
			StagedLink(
				produced_batch=produced_batch,
				direction=PRODUCED,
				batch=produced_batch,
				item=staged.item if staged else None,
				qty=float(staged.qty_original) if staged and staged.qty_original else 0.0,
				uom="Kg",
				legacy_order=record.get(order_key),
			)
		)
		for row in record.get("used", ()):
			used_rows += 1
			links.append(
				StagedLink(
					produced_batch=produced_batch,
					direction=CONSUMED,
					batch=row["batch"],
					item=row.get("product"),
					qty=float(row.get("quantity") or 0),
					uom=row.get("uom") or "Kg",
					legacy_order=record.get(order_key),
				)
			)
	return links, used_rows, produced_rows


_EXTRACTORS = {
	"qcadoo": extract_qcadoo,
	"ofbiz": extract_ofbiz,
	"erpnext": extract_erpnext,
}


def extract_source(source: str, fixture: str | Path | None = None) -> W2Extract:
	"""Extract one W2 source (`qcadoo` / `ofbiz` / `erpnext`)."""
	if source not in _EXTRACTORS:
		raise ValueError(f"unknown W2 migration source: {source!r}")
	return _EXTRACTORS[source](fixture)


def extract_all(fixture_directory: str | Path | None = None) -> dict[str, W2Extract]:
	"""Extract all three plants; `fixture_directory` overrides the committed pilot dir."""
	result: dict[str, W2Extract] = {}
	for source in SOURCES:
		fixture = None
		if fixture_directory is not None:
			fixture = Path(fixture_directory) / DEFAULT_FIXTURES[source]
		result[source] = extract_source(source, fixture)
	return result
