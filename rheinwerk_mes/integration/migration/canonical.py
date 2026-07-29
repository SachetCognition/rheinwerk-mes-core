"""The canonical master-data import format (W0-5, URS-W0-008…011).

One format for every source, so the importer, re-exporter and reconciliation
never learn a source dialect. Serialisation is **deterministic** (URS-W0-018): records
are ordered by (entity, natural key), mappings are key-sorted and no timestamp or
run identifier enters the extract file — repeated extraction over unchanged fixtures
is therefore byte-identical.

Entity set (CDM-03 item/UoM/warehouse, CDM-08 work centre, CDM-04 recipe header):

| Entity | Natural key | Target |
|---|---|---|
| `item` | `item_code` | anchor `Item` |
| `uom_conversion` | `item_code|uom` | anchor `UOM Conversion Detail` on `Item` |
| `work_centre` | `workstation_name` | anchor `Workstation` |
| `warehouse` | `warehouse_name` | anchor `Warehouse` |
| `recipe_header` | `recipe_code` | extract-only in W0 (recipe governance lands in W1) |

`direct_fields` records, per entity, the fields a source maps with the CDM `=`
(direct) legend; the reconciliation checksums exactly those (URS-W0-009).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

FORMAT_VERSION = "1.0"

ENTITY_ORDER: tuple[str, ...] = (
	"item",
	"uom_conversion",
	"work_centre",
	"warehouse",
	"recipe_header",
)

#: Entities whose counts the round-trip reconciliation reports (URS-W0-011 AC-1).
RECONCILED_ENTITIES: tuple[str, ...] = ("item", "uom_conversion", "work_centre", "warehouse")

SOURCE_SYSTEMS = {
	"qcadoo": "Qcadoo",
	"ofbiz": "OFBiz",
	"erpnext": "ERPNext Legacy",
}


@dataclass(frozen=True)
class CanonicalRecord:
	"""One master-data record in the canonical import format."""

	entity: str
	key: str
	fields: dict[str, Any]
	source_entity: str
	source_identifier: str

	def as_dict(self) -> dict[str, Any]:
		return {
			"entity": self.entity,
			"key": self.key,
			"fields": dict(sorted(self.fields.items())),
			"source_entity": self.source_entity,
			"source_identifier": self.source_identifier,
		}

	@classmethod
	def from_dict(cls, payload: dict[str, Any]) -> CanonicalRecord:
		return cls(
			entity=payload["entity"],
			key=payload["key"],
			fields=dict(payload["fields"]),
			source_entity=payload["source_entity"],
			source_identifier=payload["source_identifier"],
		)


@dataclass(frozen=True)
class MigrationException:
	"""A source record that cannot be mapped and is reported, never defaulted.

	URS-W0-010 AC-2: an unmappable unit of measure lands here instead of silently
	falling back to the stock UoM.
	"""

	entity: str
	source_identifier: str
	reason: str
	detail: str = ""

	def as_dict(self) -> dict[str, Any]:
		return {
			"entity": self.entity,
			"source_identifier": self.source_identifier,
			"reason": self.reason,
			"detail": self.detail,
		}

	@classmethod
	def from_dict(cls, payload: dict[str, Any]) -> MigrationException:
		return cls(
			entity=payload["entity"],
			source_identifier=payload["source_identifier"],
			reason=payload["reason"],
			detail=payload.get("detail", ""),
		)


@dataclass(frozen=True)
class CanonicalExtract:
	"""A source's complete master-data extract."""

	source: str
	records: tuple[CanonicalRecord, ...] = ()
	exceptions: tuple[MigrationException, ...] = ()
	direct_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)

	@property
	def source_system(self) -> str:
		"""The `Legacy Ref.source_system` value for this source."""
		return SOURCE_SYSTEMS[self.source]

	def of(self, entity: str) -> tuple[CanonicalRecord, ...]:
		return tuple(record for record in self.records if record.entity == entity)

	def counts(self) -> dict[str, int]:
		return {entity: len(self.of(entity)) for entity in ENTITY_ORDER if self.of(entity)}

	def record(self, entity: str, key: str) -> CanonicalRecord | None:
		for candidate in self.records:
			if candidate.entity == entity and candidate.key == key:
				return candidate
		return None

	def sorted_records(self) -> tuple[CanonicalRecord, ...]:
		return tuple(sorted(self.records, key=lambda record: (ENTITY_ORDER.index(record.entity), record.key)))

	def as_dict(self) -> dict[str, Any]:
		return {
			"format_version": FORMAT_VERSION,
			"source": self.source,
			"source_system": self.source_system,
			"direct_fields": {
				entity: sorted(fields) for entity, fields in sorted(self.direct_fields.items())
			},
			"records": [record.as_dict() for record in self.sorted_records()],
			"exceptions": [
				exception.as_dict()
				for exception in sorted(
					self.exceptions, key=lambda item: (item.entity, item.source_identifier, item.reason)
				)
			],
		}

	def to_json(self) -> str:
		"""Deterministic serialisation of the extract (URS-W0-018)."""
		return json.dumps(self.as_dict(), indent="\t", sort_keys=True, ensure_ascii=False) + "\n"

	@classmethod
	def from_dict(cls, payload: dict[str, Any]) -> CanonicalExtract:
		return cls(
			source=payload["source"],
			records=tuple(CanonicalRecord.from_dict(item) for item in payload["records"]),
			exceptions=tuple(MigrationException.from_dict(item) for item in payload.get("exceptions", [])),
			direct_fields={
				entity: tuple(fields) for entity, fields in payload.get("direct_fields", {}).items()
			},
		)

	@classmethod
	def from_json(cls, text: str) -> CanonicalExtract:
		return cls.from_dict(json.loads(text))


def checksum(extract: CanonicalExtract, entity: str) -> str:
	"""SHA-256 over the `=`-mapped (direct) fields of one entity (URS-W0-011)."""
	direct = tuple(sorted(extract.direct_fields.get(entity, ())))
	payload = [
		[record.key, {name: record.fields.get(name) for name in direct}]
		for record in extract.sorted_records()
		if record.entity == entity
	]
	blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
	return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def spot_check_sample(keys: list[str], *, fraction: float = 0.05, minimum: int = 10) -> list[str]:
	"""Deterministic 5 % field-level spot-check sample, at least `minimum` records.

	`docs/urs/URS-W0-foundation.md` §5: "field-level spot checks on a deterministic 5 %
	sample (minimum 10 records) per entity". Sampling is evenly spaced over the sorted
	keys so the same fixtures always yield the same sample.
	"""
	ordered = sorted(keys)
	if not ordered:
		return []
	size = max(minimum, -(-len(ordered) * int(fraction * 100) // 100))
	size = min(size, len(ordered))
	step = len(ordered) / size
	sampled = [ordered[min(len(ordered) - 1, int(index * step))] for index in range(size)]
	return sorted(dict.fromkeys(sampled))
