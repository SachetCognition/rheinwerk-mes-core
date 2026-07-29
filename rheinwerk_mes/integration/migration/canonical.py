"""The canonical master-data import format (W0-5).

One format for all legacy sources, so the importer never learns a source dialect.
Serialisation is deterministic: records are ordered by (entity, natural key), mappings are
key-sorted and neither a timestamp nor a run identifier enters the extract file — repeated
extraction over unchanged fixtures is therefore byte-identical.

| Entity | Natural key | Target |
|---|---|---|
| `item` | `item_code` | anchor `Item` |
| `work_centre` | `workstation_name` | anchor `Workstation` |
| `warehouse` | `warehouse_name` | anchor `Warehouse` |

`direct_fields` records, per entity, the fields a source maps with the CDM `=` (direct)
legend, so a later reconciliation (URS-W0-011) can checksum exactly those.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

FORMAT_VERSION = "1.0"

ENTITY_ORDER: tuple[str, ...] = ("item", "work_centre", "warehouse")

#: Source key → `source_system` label carried into the target as the legacy reference.
SOURCE_SYSTEMS = {"ofbiz": "OFBiz"}


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
	"""A source record that cannot be mapped, and is reported instead of defaulted.

	URS-W0-010 AC-2: a Product whose unit of measure has no canonical equivalent lands
	here rather than silently falling back to a stock UoM.
	"""

	entity: str
	source_entity: str
	source_identifier: str
	reason: str
	detail: str = ""

	def as_dict(self) -> dict[str, Any]:
		return {
			"entity": self.entity,
			"source_entity": self.source_entity,
			"source_identifier": self.source_identifier,
			"reason": self.reason,
			"detail": self.detail,
		}

	@classmethod
	def from_dict(cls, payload: dict[str, Any]) -> MigrationException:
		return cls(
			entity=payload["entity"],
			source_entity=payload["source_entity"],
			source_identifier=payload["source_identifier"],
			reason=payload["reason"],
			detail=payload.get("detail", ""),
		)


@dataclass(frozen=True)
class CanonicalExtract:
	"""One source's complete master-data extract."""

	source: str
	records: tuple[CanonicalRecord, ...] = ()
	exceptions: tuple[MigrationException, ...] = ()
	direct_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)

	@property
	def source_system(self) -> str:
		return SOURCE_SYSTEMS[self.source]

	def of(self, entity: str) -> tuple[CanonicalRecord, ...]:
		return tuple(record for record in self.sorted_records() if record.entity == entity)

	def record(self, entity: str, key: str) -> CanonicalRecord | None:
		for candidate in self.records:
			if candidate.entity == entity and candidate.key == key:
				return candidate
		return None

	def counts(self) -> dict[str, int]:
		return {entity: len(self.of(entity)) for entity in ENTITY_ORDER if self.of(entity)}

	def sorted_records(self) -> tuple[CanonicalRecord, ...]:
		return tuple(sorted(self.records, key=lambda record: (ENTITY_ORDER.index(record.entity), record.key)))

	def sorted_exceptions(self) -> tuple[MigrationException, ...]:
		return tuple(
			sorted(
				self.exceptions,
				key=lambda item: (item.entity, item.source_identifier, item.reason),
			)
		)

	def as_dict(self) -> dict[str, Any]:
		return {
			"format_version": FORMAT_VERSION,
			"source": self.source,
			"source_system": self.source_system,
			"direct_fields": {
				entity: sorted(fields) for entity, fields in sorted(self.direct_fields.items())
			},
			"records": [record.as_dict() for record in self.sorted_records()],
			"exceptions": [exception.as_dict() for exception in self.sorted_exceptions()],
		}

	def to_json(self) -> str:
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
