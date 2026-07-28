"""Site-backed reconciliation for the W2 migration (URS-W2-030…032 criteria).

Each URS carries reconciliation criteria that must be *code, not prose*. This module reads
the target site and compares it to the staging `W2Extract`, emitting a German-first
`PASS`/`FAIL` report the wave evidence pack can cite. Because staging is derived purely from
the committed legacy fixtures, a target-vs-staging comparison is a target-vs-legacy
reconciliation.

Criteria implemented (per plant unless noted):

* per-plant batch counts (URS-W2-030);
* `qa_state` distribution vs the legacy dispositions (URS-W2-030 / URS-W2-032);
* deterministic 100-record identity spot-check (URS-W2-030);
* `(batch_id, item, expiry_date)` checksum (URS-W2-030);
* Quarantined/Blocked counts vs legacy flagged resources/batches (URS-W2-032);
* genealogy link counts by direction vs the legacy used/produced rows (URS-W2-031);
* zero orphan links (URS-W2-031);
* 50-tree backward-trace spot-check (URS-W2-031);
* trace-boundary date recorded for Plant B (URS-W2-031);
* zero Quality Inspection records before the migration cut date, global (URS-W2-032).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import frappe

from rheinwerk_mes.genealogy import trace
from rheinwerk_mes.integration.migration.w2.model import (
	BLOCKED,
	CONSUMED,
	CUT_DATE,
	PRODUCED,
	QUARANTINED,
	RELEASED,
	W2Extract,
	batch_identity_checksum,
	sample_batch_ids,
)

PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class Check:
	"""One reconciliation criterion outcome."""

	key: str
	label: str
	status: str
	source: Any
	target: Any
	detail: str = ""

	@classmethod
	def compare(cls, key: str, label: str, source: Any, target: Any, detail: str = "") -> Check:
		return cls(key, label, PASS if source == target else FAIL, source, target, detail)


@dataclass(frozen=True)
class PlantReconciliation:
	plant: str
	source: str
	checks: tuple[Check, ...]
	expiry_conflicts: tuple[str, ...] = ()
	trace_boundary_date: str | None = None

	@property
	def status(self) -> str:
		return FAIL if any(check.status == FAIL for check in self.checks) else PASS


@dataclass(frozen=True)
class W2ReconciliationReport:
	plants: tuple[PlantReconciliation, ...]
	quality_inspection_check: Check
	run_ids: dict[str, dict[str, str]]
	generated_at: str = ""

	@property
	def status(self) -> str:
		if self.quality_inspection_check.status == FAIL:
			return FAIL
		return FAIL if any(plant.status == FAIL for plant in self.plants) else PASS

	def to_markdown(self) -> str:
		lines = [
			"# Abstimmbericht W2-Migration — offene Chargen, Genealogie, Qualitätskennzeichen",
			"",
			f"- **Status:** {self.status}",
			f"- **Erzeugt:** {self.generated_at}",
			f"- **Schnittdatum Qualitätsprüfungen:** {_de(CUT_DATE)}",
			"",
			"_URS-W2-030 (Chargen-Zusammenführung) · URS-W2-031 (Genealogie) · "
			"URS-W2-032 (Qualitätskennzeichen als Zustandshistorie)._",
			"",
		]
		for plant in self.plants:
			lines += [
				f"## Werk {plant.plant} ({plant.source}) — {plant.status}",
				"",
				"| Kriterium | Quelle (Legacy) | Ziel (ERPNext) | Status | Detail |",
				"|---|---|---|---|---|",
			]
			for check in plant.checks:
				lines.append(
					f"| {check.label} | {check.source} | {check.target} | {check.status} | {check.detail} |"
				)
			if plant.expiry_conflicts:
				lines += ["", "**Ablaufdatum-Konflikte (frühestes gewählt):**"]
				lines += [f"- {conflict}" for conflict in plant.expiry_conflicts]
			lines.append("")
		qi = self.quality_inspection_check
		lines += [
			"## Qualitätsprüfungen (global)",
			"",
			"| Kriterium | Erwartet | Gefunden | Status | Detail |",
			"|---|---|---|---|---|",
			f"| {qi.label} | {qi.source} | {qi.target} | {qi.status} | {qi.detail} |",
			"",
			"## Läufe (rollback-fähig je Schritt)",
			"",
			"| Werk | Chargen | Genealogie | Zustand |",
			"|---|---|---|---|",
		]
		for plant in self.plants:
			ids = self.run_ids.get(plant.source, {})
			lines.append(
				f"| {plant.plant} | `{ids.get('batches', '—')}` | `{ids.get('links', '—')}` | "
				f"`{ids.get('state', '—')}` |"
			)
		return "\n".join(lines) + "\n"


def _de(iso_date: str | None) -> str | None:
	if not iso_date:
		return None
	return datetime.strptime(str(iso_date)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")


def _existing(batch_ids: list[str]) -> list[str]:
	return [b for b in batch_ids if frappe.db.exists("Batch", b)]


def _expected_backward(extract: W2Extract, root: str) -> set[str]:
	"""Legacy backward-trace node set of `root` from the staged consumed adjacency."""
	adjacency: dict[str, list[str]] = {}
	for link in extract.consumed_links():
		adjacency.setdefault(link.produced_batch, []).append(link.batch)
	seen = {root}
	frontier = [root]
	while frontier:
		current = frontier.pop()
		for child in adjacency.get(current, ()):
			if child not in seen:
				seen.add(child)
				frontier.append(child)
	return seen


def reconcile_plant(extract: W2Extract) -> PlantReconciliation:
	staged_ids = [staged.batch_id for staged in extract.batches]
	present = _existing(staged_ids)
	checks: list[Check] = []

	# --- URS-W2-030: counts, checksum, identity spot-check -----------------------------
	checks.append(
		Check.compare(
			"batch_count",
			"Chargenanzahl (zusammengeführt)",
			len(staged_ids),
			len(present),
			detail=f"{len(extract.incomplete_boundary_batches)} unvollständig (Spurgrenze)",
		)
	)

	target_identity = [
		frappe.db.get_value("Batch", b, ["name as batch_id", "item", "expiry_date"], as_dict=True)
		for b in present
	]
	checks.append(
		Check.compare(
			"identity_checksum",
			"Prüfsumme (batch_id, item, Ablaufdatum)",
			batch_identity_checksum(extract.batches)[:12],
			batch_identity_checksum([dict(row) for row in target_identity])[:12],
		)
	)

	spot_ids = sample_batch_ids(staged_ids, count=100)
	identity_mismatches = _identity_spot_check(extract, spot_ids)
	checks.append(
		Check(
			"identity_spot_check",
			f"Stichprobe Identität ({len(spot_ids)} Sätze)",
			PASS if not identity_mismatches else FAIL,
			len(spot_ids),
			len(spot_ids) - len(identity_mismatches),
			detail="; ".join(identity_mismatches) if identity_mismatches else "keine Abweichung",
		)
	)

	# --- URS-W2-030 / URS-W2-032: qa_state distribution + flag counts ------------------
	source_dist = extract.qa_state_distribution()
	target_dist = _target_distribution(present)
	checks.append(
		Check.compare(
			"qa_state_distribution",
			"qa_state-Verteilung",
			_fmt_dist(source_dist),
			_fmt_dist(target_dist),
		)
	)
	source_flagged = {
		QUARANTINED: source_dist.get(QUARANTINED, 0),
		BLOCKED: source_dist.get(BLOCKED, 0),
	}
	target_flagged = {QUARANTINED: target_dist.get(QUARANTINED, 0), BLOCKED: target_dist.get(BLOCKED, 0)}
	checks.append(
		Check.compare(
			"flagged_counts",
			"Quarantäne/Gesperrt vs. Legacy-Kennzeichen",
			_fmt_dist(source_flagged),
			_fmt_dist(target_flagged),
		)
	)

	# --- URS-W2-031: link counts, orphans, 50-tree trace, boundary ---------------------
	target_consumed, target_produced, orphans = _link_stats(present)
	checks.append(
		Check.compare(
			"consumed_links",
			"Genealogie-Kanten (verbraucht)",
			extract.source_used_rows,
			target_consumed,
		)
	)
	checks.append(
		Check.compare(
			"produced_links",
			"Genealogie-Kanten (produziert)",
			extract.source_produced_rows,
			target_produced,
		)
	)
	checks.append(
		Check.compare("orphan_links", "Verwaiste Kanten", 0, len(orphans), detail=", ".join(sorted(orphans)))
	)

	produced_roots = sorted(
		{link.produced_batch for link in extract.produced_links() if link.produced_batch in present}
	)
	trace_sample = sample_batch_ids(produced_roots, count=50)
	trace_mismatches = _trace_spot_check(extract, trace_sample)
	checks.append(
		Check(
			"backward_trace",
			f"Rückwärts-Trace-Stichprobe ({len(trace_sample)} Bäume)",
			PASS if not trace_mismatches else FAIL,
			len(trace_sample),
			len(trace_sample) - len(trace_mismatches),
			detail="; ".join(trace_mismatches) if trace_mismatches else "Knotenmengen identisch",
		)
	)

	if extract.incomplete_boundary_batches:
		boundary_ok = all(
			frappe.db.get_value("Batch", b, "genealogy_incomplete")
			and str(frappe.db.get_value("Batch", b, "trace_boundary_date") or "")[:10]
			== extract.trace_boundary_date
			for b in extract.incomplete_boundary_batches
			if b in present
		)
		checks.append(
			Check(
				"trace_boundary",
				"Spurgrenze erfasst (Plant B)",
				PASS if boundary_ok else FAIL,
				_de(extract.trace_boundary_date),
				_de(extract.trace_boundary_date) if boundary_ok else "fehlt",
				detail=", ".join(sorted(extract.incomplete_boundary_batches)),
			)
		)

	return PlantReconciliation(
		plant=extract.plant,
		source=extract.source,
		checks=tuple(checks),
		expiry_conflicts=extract.expiry_conflicts,
		trace_boundary_date=extract.trace_boundary_date,
	)


def _identity_spot_check(extract: W2Extract, batch_ids: list[str]) -> list[str]:
	mismatches: list[str] = []
	for batch_id in batch_ids:
		staged = extract.batch(batch_id)
		if staged is None or not frappe.db.exists("Batch", batch_id):
			mismatches.append(f"{batch_id}: fehlt")
			continue
		row = frappe.db.get_value(
			"Batch", batch_id, ["item", "expiry_date", "genealogy_incomplete"], as_dict=True
		)
		if row.item != staged.item:
			mismatches.append(f"{batch_id}: Artikel {row.item} ≠ {staged.item}")
		if str(row.expiry_date or "")[:10] != (staged.expiry_date or ""):
			mismatches.append(f"{batch_id}: Ablaufdatum {row.expiry_date} ≠ {staged.expiry_date}")
		ref_count = frappe.db.count("Legacy Ref", {"parent": batch_id, "parenttype": "Batch"})
		if ref_count < len(staged.legacy_refs):
			mismatches.append(f"{batch_id}: legacy_refs {ref_count} < {len(staged.legacy_refs)}")
	return mismatches


def _target_distribution(batch_ids: list[str]) -> dict[str, int]:
	distribution = {QUARANTINED: 0, RELEASED: 0, BLOCKED: 0}
	for batch_id in batch_ids:
		state = frappe.db.get_value("Batch", batch_id, "qa_state") or QUARANTINED
		distribution[state] = distribution.get(state, 0) + 1
	return distribution


def _fmt_dist(distribution: dict[str, int]) -> str:
	return ", ".join(f"{state}={distribution.get(state, 0)}" for state in (QUARANTINED, RELEASED, BLOCKED))


def _link_stats(batch_ids: list[str]) -> tuple[int, int, list[str]]:
	if not batch_ids:
		return 0, 0, []
	rows = frappe.get_all(
		"Genealogy Link",
		filters={"parent": ("in", batch_ids), "parenttype": "Batch"},
		fields=["direction", "batch"],
	)
	consumed = sum(1 for row in rows if row.direction == CONSUMED)
	produced = sum(1 for row in rows if row.direction == PRODUCED)
	orphans = [row.batch for row in rows if not frappe.db.exists("Batch", row.batch)]
	return consumed, produced, orphans


def _trace_spot_check(extract: W2Extract, roots: list[str]) -> list[str]:
	mismatches: list[str] = []
	for root in roots:
		expected = _expected_backward(extract, root)
		try:
			actual = {node["batch"] for node in trace.flatten(trace.backward(root))}
		except frappe.DoesNotExistError:
			# A link points at a batch that no longer exists — an orphan the trace cannot
			# resolve; the orphan-link check reports it, here it is a tree divergence.
			mismatches.append(f"{root}: verwaiste Kante — Ziel-Charge fehlt")
			continue
		if expected != actual:
			mismatches.append(f"{root}: erwartet {sorted(expected)} ≠ {sorted(actual)}")
	return mismatches


def quality_inspection_check() -> Check:
	"""Zero Quality Inspection records may predate the migration cut date (URS-W2-032 AC-2)."""
	if not frappe.db.exists("DocType", "Quality Inspection"):
		return Check(
			"no_pre_cut_qi", "Keine QP vor Schnittdatum", PASS, 0, 0, detail="DocType nicht installiert"
		)
	field = "report_date" if frappe.get_meta("Quality Inspection").get_field("report_date") else "creation"
	count = frappe.db.count("Quality Inspection", {field: ("<", CUT_DATE)})
	return Check(
		"no_pre_cut_qi",
		"Keine QP vor Schnittdatum",
		PASS if count == 0 else FAIL,
		0,
		count,
		detail=f"Feld {field} < {_de(CUT_DATE)}",
	)


def build_report(
	extracts: dict[str, W2Extract],
	run_ids: dict[str, dict[str, str]] | None = None,
) -> W2ReconciliationReport:
	"""Reconcile every plant and assemble the citable pilot report artefact."""
	plants = tuple(reconcile_plant(extract) for extract in extracts.values())
	return W2ReconciliationReport(
		plants=plants,
		quality_inspection_check=quality_inspection_check(),
		run_ids=run_ids or {},
		generated_at=datetime.now(tz=timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
	)
