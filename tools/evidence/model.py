"""Evidence model: backlog item → dossier citation → URS IDs → test IDs (URS-W0-013).

Status semantics (AC-1, AC-2):

* `complete` — the item has URS coverage, every mapped TC is implemented by at least one
  test (or recorded as manual evidence), and nothing is missing.
* `evidence-incomplete` — the item is linked to URS/TC IDs but at least one mapped TC has
  no evidence yet. The row is **reported and flagged**, never omitted.
* `unlinked` — the item has no URS coverage at all, or its URS requirements map to no test
  case. This breaks the audit spine and makes the generator exit non-zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .parsers import (
	BacklogItem,
	EvidenceCitation,
	collect_test_evidence,
	parse_backlog,
	parse_manual_evidence,
	parse_traceability,
	parse_urs_by_backlog_item,
)

STATUS_COMPLETE = "complete"
STATUS_INCOMPLETE = "evidence-incomplete"
STATUS_UNLINKED = "unlinked"


@dataclass(frozen=True)
class EvidenceRow:
	"""One backlog item with its full evidence chain."""

	backlog: BacklogItem
	urs_ids: tuple[str, ...]
	tc_ids: tuple[str, ...]
	evidence: dict[str, tuple[str, ...]]
	status: str
	missing_tc_ids: tuple[str, ...]
	notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Report:
	"""A wave's evidence pack."""

	wave: str
	rows: tuple[EvidenceRow, ...]
	sources: dict[str, str]
	urs_titles: dict[str, str] = field(default_factory=dict)

	@property
	def unlinked(self) -> tuple[EvidenceRow, ...]:
		return tuple(row for row in self.rows if row.status == STATUS_UNLINKED)

	@property
	def incomplete(self) -> tuple[EvidenceRow, ...]:
		return tuple(row for row in self.rows if row.status == STATUS_INCOMPLETE)

	@property
	def complete(self) -> tuple[EvidenceRow, ...]:
		return tuple(row for row in self.rows if row.status == STATUS_COMPLETE)

	def row(self, backlog_id: str) -> EvidenceRow:
		for row in self.rows:
			if row.backlog.id == backlog_id:
				return row
		raise KeyError(backlog_id)


def _wave_document(directory: Path, prefix: str, wave: str) -> Path:
	pattern = f"{prefix}{wave}-*.md" if prefix else f"{wave}-*.md"
	matches = sorted(directory.glob(pattern))
	if not matches:
		raise FileNotFoundError(f"no document matching {pattern} in {directory}")
	return matches[0]


def _evidence_index(entries: list[EvidenceCitation]) -> dict[str, list[EvidenceCitation]]:
	index: dict[str, list[EvidenceCitation]] = {}
	for entry in entries:
		for tc_id in entry.tc_ids:
			index.setdefault(tc_id, []).append(entry)
	return index


def build_report(
	repo_root: Path,
	wave: str,
	*,
	evidence_index: dict[str, list[EvidenceCitation]] | None = None,
) -> Report:
	"""Build the evidence report for `wave` from the committed specs and test suite.

	`evidence_index` is injectable so tests can exercise the flagging behaviour required by
	URS-W0-013 AC-2 (a backlog item stripped of its test link) without mutating the repo.
	"""
	backlog_path = _wave_document(repo_root / "docs" / "waves", "", wave)
	urs_path = _wave_document(repo_root / "docs" / "urs", "URS-", wave)
	tst_path = _wave_document(repo_root / "docs" / "test", "TST-", wave)

	backlog = parse_backlog(backlog_path)
	urs_by_item, urs_titles = parse_urs_by_backlog_item(urs_path)
	traceability = parse_traceability(tst_path)

	if evidence_index is None:
		entries = collect_test_evidence(repo_root / "tests", repo_root)
		entries += parse_manual_evidence(repo_root / "docs" / "evidence" / "manual-evidence.md", repo_root)
		evidence_index = _evidence_index(entries)

	rows: list[EvidenceRow] = []
	for item in backlog:
		urs_ids = tuple(urs_by_item.get(item.id, ()))
		tc_ids: list[str] = []
		for urs_id in urs_ids:
			for tc_id in traceability.get(urs_id, ()):
				if tc_id not in tc_ids:
					tc_ids.append(tc_id)

		evidence: dict[str, tuple[str, ...]] = {}
		missing: list[str] = []
		for tc_id in tc_ids:
			locations = tuple(entry.location for entry in evidence_index.get(tc_id, ()))
			if locations:
				evidence[tc_id] = locations
			else:
				missing.append(tc_id)

		notes: list[str] = []
		if not urs_ids:
			status = STATUS_UNLINKED
			notes.append("no URS requirement references this backlog item")
		elif not tc_ids:
			status = STATUS_UNLINKED
			notes.append("URS requirements are mapped to no test case in the TST traceability matrix")
		elif missing:
			status = STATUS_INCOMPLETE
			notes.append("no test cites " + ", ".join(missing))
		else:
			status = STATUS_COMPLETE

		manual = sorted(
			{
				entry.location
				for tc_id in tc_ids
				for entry in evidence_index.get(tc_id, ())
				if entry.kind == "manual"
			}
		)
		if manual:
			notes.append(f"{len(manual)} test case(s) covered by manual evidence")

		rows.append(
			EvidenceRow(
				backlog=item,
				urs_ids=urs_ids,
				tc_ids=tuple(tc_ids),
				evidence=evidence,
				status=status,
				missing_tc_ids=tuple(missing),
				notes=tuple(notes),
			)
		)

	sources = {
		"backlog": backlog_path.relative_to(repo_root).as_posix(),
		"urs": urs_path.relative_to(repo_root).as_posix(),
		"tst": tst_path.relative_to(repo_root).as_posix(),
	}
	return Report(wave=wave, rows=tuple(rows), sources=sources, urs_titles=urs_titles)
