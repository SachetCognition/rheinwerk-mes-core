"""Canonical W2 staging model for the open-batch / genealogy / quality migration.

One staging shape for all three plants, so the loaders, reconcilers and rollback never
learn a source dialect (mirrors the W0-5 `canonical.CanonicalExtract` split). The staging
is produced offline by `extract.py` from the committed pilot fixtures — no extractor talks
to a Frappe site, so the dual-model merge (URS-W2-030), the TrackingRecord → link fold
(URS-W2-031) and the legacy-flag → qa_state map (URS-W2-032) are all testable without a
site and are deterministic over unchanged fixtures (URS-W0-018 contract, inherited).

`qa_state` tokens are defined locally rather than imported from
`rheinwerk_mes.genealogy.qa_state` (which imports `frappe`), so this module stays import-safe
offline. They must equal the genealogy module's constants — asserted in the acceptance suite.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from rheinwerk_mes.integration.migration.canonical import SOURCE_SYSTEMS, spot_check_sample

# qa_state vocabulary (must mirror rheinwerk_mes.genealogy.qa_state).
QUARANTINED = "Quarantined"
RELEASED = "Released"
BLOCKED = "Blocked"

CONSUMED = "consumed"
PRODUCED = "produced"

#: Migration cut date: no Quality Inspection record may carry an inspection date before it
#: (URS-W2-032 AC-2 — legacy quality flags migrate as qa_state history only, never as
#: synthetic parametric inspections).
CUT_DATE = "2026-01-01"


@dataclass(frozen=True)
class LegacyRef:
	"""One preserved legacy identifier of a batch (URS-W2-007 · `Legacy Ref` row)."""

	source_system: str
	source_entity: str
	source_identifier: str

	def as_dict(self) -> dict[str, str]:
		return {
			"source_system": self.source_system,
			"source_entity": self.source_entity,
			"source_identifier": self.source_identifier,
		}


@dataclass(frozen=True)
class StagedBatch:
	"""A canonical Batch as merged from the legacy dual model (URS-W2-030)."""

	batch_id: str
	item: str
	expiry_date: str | None
	qa_state: str
	genealogy_incomplete: bool
	legacy_refs: tuple[LegacyRef, ...]
	#: Raw legacy disposition token, kept for the qa_state-distribution reconciliation
	#: (`tracked` / `blocked` / `blocked_for_quality_control` / `disabled` / `none`).
	legacy_state: str
	manufacturing_date: str | None = None
	trace_boundary_date: str | None = None
	qty_original: float | None = None
	supplier_batch_no: str | None = None
	#: German-first note citing the legacy flag as the origin of the disposition, written
	#: to `qa_state_history` by the state-assignment step (URS-W2-032 AC-1).
	qa_state_origin: str | None = None
	#: Populated when two legacy lots of one merged batch disagreed on expiry — the
	#: earliest wins and the conflict is reported (URS-W2-030 AC-3).
	expiry_conflict: str | None = None

	def as_dict(self) -> dict[str, Any]:
		return {
			"batch_id": self.batch_id,
			"item": self.item,
			"expiry_date": self.expiry_date,
			"qa_state": self.qa_state,
			"genealogy_incomplete": self.genealogy_incomplete,
			"legacy_state": self.legacy_state,
			"manufacturing_date": self.manufacturing_date,
			"trace_boundary_date": self.trace_boundary_date,
			"qty_original": self.qty_original,
			"supplier_batch_no": self.supplier_batch_no,
			"qa_state_origin": self.qa_state_origin,
			"expiry_conflict": self.expiry_conflict,
			"legacy_refs": [ref.as_dict() for ref in self.legacy_refs],
		}


@dataclass(frozen=True)
class StagedLink:
	"""One genealogy edge folded from a TrackingRecord / WorkEffort tree (URS-W2-031).

	Written onto the produced batch: one `produced` self-edge and n `consumed` edges, the
	Qcadoo `TrackingRecordFields` shape re-expressed on the produced batch (see
	`rheinwerk_mes.genealogy.links`).
	"""

	produced_batch: str
	direction: str
	batch: str
	item: str | None
	qty: float
	uom: str | None
	legacy_order: str | None = None

	def as_dict(self) -> dict[str, Any]:
		return {
			"produced_batch": self.produced_batch,
			"direction": self.direction,
			"batch": self.batch,
			"item": self.item,
			"qty": self.qty,
			"uom": self.uom,
			"legacy_order": self.legacy_order,
		}


@dataclass(frozen=True)
class W2Extract:
	"""A plant's complete open-batch + genealogy + quality staging extract."""

	plant: str
	source: str
	batches: tuple[StagedBatch, ...] = ()
	links: tuple[StagedLink, ...] = ()
	expiry_conflicts: tuple[str, ...] = ()
	trace_boundary_date: str | None = None
	#: Legacy used/produced row counts (lotId present) — the link-count reconciliation base.
	source_used_rows: int = 0
	source_produced_rows: int = 0
	#: Produced batches flagged incomplete because a consumed row had no lotId (URS-W2-031 AC-2).
	incomplete_boundary_batches: tuple[str, ...] = ()
	notes: tuple[str, ...] = field(default_factory=tuple)

	@property
	def source_system(self) -> str:
		return SOURCE_SYSTEMS[self.source]

	def batch(self, batch_id: str) -> StagedBatch | None:
		for candidate in self.batches:
			if candidate.batch_id == batch_id:
				return candidate
		return None

	def sorted_batches(self) -> tuple[StagedBatch, ...]:
		return tuple(sorted(self.batches, key=lambda b: b.batch_id))

	def consumed_links(self) -> tuple[StagedLink, ...]:
		return tuple(link for link in self.links if link.direction == CONSUMED)

	def produced_links(self) -> tuple[StagedLink, ...]:
		return tuple(link for link in self.links if link.direction == PRODUCED)

	def qa_state_distribution(self) -> dict[str, int]:
		"""Count of staged batches per qa_state (reconciled against the target site)."""
		distribution = {QUARANTINED: 0, RELEASED: 0, BLOCKED: 0}
		for staged in self.batches:
			distribution[staged.qa_state] = distribution.get(staged.qa_state, 0) + 1
		return distribution

	def flagged_batch_ids(self) -> tuple[str, ...]:
		"""Batches whose disposition came from a legacy quality flag (URS-W2-032)."""
		return tuple(
			sorted(staged.batch_id for staged in self.batches if staged.qa_state in (QUARANTINED, BLOCKED))
		)

	def as_dict(self) -> dict[str, Any]:
		return {
			"plant": self.plant,
			"source": self.source,
			"source_system": self.source_system,
			"trace_boundary_date": self.trace_boundary_date,
			"source_used_rows": self.source_used_rows,
			"source_produced_rows": self.source_produced_rows,
			"incomplete_boundary_batches": sorted(self.incomplete_boundary_batches),
			"expiry_conflicts": sorted(self.expiry_conflicts),
			"batches": [staged.as_dict() for staged in self.sorted_batches()],
			"links": [
				link.as_dict()
				for link in sorted(
					self.links, key=lambda link: (link.produced_batch, link.direction, link.batch)
				)
			],
		}


def batch_identity_checksum(batches: tuple[StagedBatch, ...] | list[dict[str, Any]]) -> str:
	"""SHA-256 over the `(batch_id, item, expiry_date)` tuples (URS-W2-030 reconciliation).

	Accepts both the staging shape (`StagedBatch`) and the target shape (list of dicts with
	the same three keys), so the staging↔target checksum comparison reads one function.
	"""
	rows: list[list[Any]] = []
	for record in batches:
		if isinstance(record, StagedBatch):
			rows.append([record.batch_id, record.item, record.expiry_date])
		else:
			rows.append([record.get("batch_id"), record.get("item"), record.get("expiry_date")])
	rows.sort(key=lambda row: (row[0] or ""))
	blob = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
	return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sample_batch_ids(batch_ids: list[str], *, count: int) -> list[str]:
	"""Deterministic spot-check sample of up to `count` batch ids (URS-W2-030/031).

	The URS asks for a 100-record (batches) and 50-tree (genealogy) spot-check; on the pilot
	subset — fewer than 100/50 records — the sample is every record, which is a strict
	superset of the requested minimum. Sampling reuses the W0-5 evenly-spaced sampler so a
	given fixture always yields the same sample.
	"""
	ordered = sorted(batch_ids)
	if len(ordered) <= count:
		return ordered
	fraction = count / len(ordered)
	return spot_check_sample(ordered, fraction=fraction, minimum=count)
