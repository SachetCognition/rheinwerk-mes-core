"""Round-trip reconciliation and PASS/FAIL reporting (URS-W0-011, TC-W0-012).

Per source and per entity the reconciliation compares the source extract with the
re-export of the target:

1. **counts** — source = imported = re-exported (AC-1);
2. **checksums** — SHA-256 over the CDM `=`-mapped fields (byte-identity, URS-W0-009);
3. **spot checks** — a deterministic 5 % sample (minimum 10 records) compared
   field-by-field, so a value drift inside an unchanged count is still caught.

Any deviation makes the report FAIL and names the offending record and field (AC-2). The
report renders as German-first markdown; dates are DD.MM.YYYY and quantities stay in the
canonical UoM (kg).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rheinwerk_mes.integration.migration.canonical import (
	RECONCILED_ENTITIES,
	CanonicalExtract,
	checksum,
	spot_check_sample,
)

PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class Difference:
	"""One reconciliation deviation, naming the record it belongs to."""

	entity: str
	key: str
	kind: str  # "missing" | "unexpected" | "field" | "checksum" | "count"
	detail: str

	def __str__(self) -> str:
		return f"{self.entity} {self.key}: {self.kind} — {self.detail}"


@dataclass(frozen=True)
class EntityReconciliation:
	"""Reconciliation result for a single entity of one source."""

	entity: str
	source_count: int
	imported_count: int
	reexported_count: int
	source_checksum: str
	reexported_checksum: str
	sample: tuple[str, ...]
	differences: tuple[Difference, ...]

	@property
	def status(self) -> str:
		return FAIL if self.differences else PASS


@dataclass(frozen=True)
class ReconciliationReport:
	"""The per-source reconciliation report (URS-W0-011)."""

	source: str
	run_id: str
	entities: tuple[EntityReconciliation, ...]
	exceptions: tuple[dict[str, Any], ...] = ()
	deferred: dict[str, int] = field(default_factory=dict)
	duration_seconds: float = 0.0

	@property
	def status(self) -> str:
		return FAIL if any(entity.status == FAIL for entity in self.entities) else PASS

	@property
	def differences(self) -> tuple[Difference, ...]:
		return tuple(difference for entity in self.entities for difference in entity.differences)

	def to_markdown(self) -> str:
		lines = [
			f"# Abstimmbericht Stammdatenmigration — {self.source}",
			"",
			f"- **Status:** {self.status}",
			f"- **Lauf:** {self.run_id}",
			f"- **Dauer:** {self.duration_seconds:.1f} s",
			"",
			"| Entität | Quelle | Importiert | Rückexport | Prüfsumme Quelle | Prüfsumme Rückexport | Stichprobe | Status |",
			"|---|---|---|---|---|---|---|---|",
		]
		for entity in self.entities:
			lines.append(
				f"| {entity.entity} | {entity.source_count} | {entity.imported_count} | "
				f"{entity.reexported_count} | `{entity.source_checksum[:12]}` | "
				f"`{entity.reexported_checksum[:12]}` | {len(entity.sample)} | {entity.status} |"
			)
		if self.deferred:
			lines += [
				"",
				"Zurückgestellt (W1, CDM-04 Rezeptfreigabe): "
				+ ", ".join(f"{entity} = {count}" for entity, count in sorted(self.deferred.items())),
			]
		if self.exceptions:
			lines += [
				"",
				"## Ausnahmen (nicht importiert)",
				"",
				"| Entität | Quell-ID | Grund | Detail |",
				"|---|---|---|---|",
			]
			for exception in self.exceptions:
				lines.append(
					f"| {exception['entity']} | `{exception['source_identifier']}` | "
					f"{exception['reason']} | {exception['detail']} |"
				)
		if self.differences:
			lines += ["", "## Abweichungen", ""]
			lines += [f"- {difference}" for difference in self.differences]
		return "\n".join(lines) + "\n"


def reconcile_entity(
	entity: str,
	source: CanonicalExtract,
	reexported: CanonicalExtract,
	imported_count: int,
) -> EntityReconciliation:
	"""Reconcile one entity: counts, checksums and the deterministic spot-check sample."""
	source_records = {record.key: record for record in source.of(entity)}
	target_records = {record.key: record for record in reexported.of(entity)}
	differences: list[Difference] = []

	for key in sorted(set(source_records) - set(target_records)):
		differences.append(Difference(entity, key, "missing", "im Zielsystem nicht vorhanden"))
	for key in sorted(set(target_records) - set(source_records)):
		differences.append(Difference(entity, key, "unexpected", "im Rückexport zusätzlich vorhanden"))

	if len(source_records) != imported_count and imported_count:
		differences.append(
			Difference(
				entity,
				"—",
				"count",
				f"Quelle {len(source_records)} ≠ importiert {imported_count}",
			)
		)

	sample = spot_check_sample(list(source_records))
	for key in sample:
		source_record = source_records[key]
		target_record = target_records.get(key)
		if target_record is None:
			continue
		for name, value in sorted(source_record.fields.items()):
			if value is None or name not in target_record.fields:
				continue
			target_value = target_record.fields.get(name)
			if isinstance(value, float) or isinstance(target_value, float):
				matches = float(value) == float(target_value or 0)
			else:
				matches = value == target_value
			if not matches:
				differences.append(
					Difference(entity, key, "field", f"{name}: Quelle {value!r} ≠ Ziel {target_value!r}")
				)

	source_checksum = checksum(source, entity)
	target_checksum = checksum(reexported, entity)
	if source_checksum != target_checksum:
		differences.append(
			Difference(entity, "—", "checksum", "Prüfsumme der direkt gemappten Felder weicht ab")
		)

	return EntityReconciliation(
		entity=entity,
		source_count=len(source_records),
		imported_count=imported_count,
		reexported_count=len(target_records),
		source_checksum=source_checksum,
		reexported_checksum=target_checksum,
		sample=tuple(sample),
		differences=tuple(differences),
	)


def reconcile(
	source: CanonicalExtract,
	reexported: CanonicalExtract,
	*,
	run_id: str,
	imported: dict[str, int] | None = None,
	deferred: dict[str, int] | None = None,
	duration_seconds: float = 0.0,
) -> ReconciliationReport:
	"""Reconcile a full round trip for one source."""
	imported = imported or {}
	entities = tuple(
		reconcile_entity(entity, source, reexported, imported.get(entity, 0))
		for entity in RECONCILED_ENTITIES
		if source.of(entity)
	)
	return ReconciliationReport(
		source=source.source,
		run_id=run_id,
		entities=entities,
		exceptions=tuple(exception.as_dict() for exception in source.exceptions),
		deferred=deferred or {},
		duration_seconds=duration_seconds,
	)
