"""Markdown and test-suite parsers for the evidence-pack generator (URS-W0-013).

The generator never keeps a second copy of the programme's traceability: it reads the
committed specs (`docs/waves/W{n}-*.md`, `docs/urs/URS-W{n}-*.md`,
`docs/test/TST-W{n}-*.md`) and the test suite itself, so a stale evidence pack is
impossible by construction.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

BACKLOG_ID = re.compile(r"^W\d+-\d+$")
URS_ID = re.compile(r"URS-W\d+-\d+")
TC_ID = re.compile(r"TC-W\d+-\d+")
#: A URS section heading names the backlog item(s) it implements in parentheses. A heading
#: may carry more than one parenthesised group — "3.9 Trace demonstration (W2-9) and
#: e-signature decision (W2-10)" — so every group is collected, not only a trailing one.
#: The group may be written bare ("(W2-9)") or spelled out with the wave's own wording
#: ("(backlog W3-3, W3-4; ADR-002)"), and may carry trailing notes after the ids.
SECTION_HEADING = re.compile(r"^#{2,4}\s")
SECTION_ITEMS = re.compile(r"\((?:backlog\s+)?(?P<items>W\d+-\d+(?:\s*[,/]\s*W\d+-\d+)*)")
URS_HEADING = re.compile(r"^####\s+(?P<urs>URS-W\d+-\d+)\s*[—-]\s*(?P<title>.+?)\s*$")


@dataclass(frozen=True)
class BacklogItem:
	"""One row of a wave backlog table."""

	id: str
	item: str
	disposition: str
	dossier_citation: str


@dataclass(frozen=True)
class EvidenceCitation:
	"""A test (or manual evidence entry) that verifies one or more test cases."""

	tc_ids: tuple[str, ...]
	location: str
	kind: str  # "test" | "manual"


def split_table_row(line: str) -> list[str]:
	"""Split a markdown table row into stripped cell values."""
	stripped = line.strip()
	if not stripped.startswith("|"):
		return []
	cells = [cell.strip() for cell in stripped.strip("|").split("|")]
	return cells


def parse_backlog(path: Path) -> list[BacklogItem]:
	"""Parse the backlog table of a wave document (`docs/waves/W{n}-*.md`)."""
	items: list[BacklogItem] = []
	for line in path.read_text(encoding="utf-8").splitlines():
		cells = split_table_row(line)
		if len(cells) < 2 or not BACKLOG_ID.match(cells[0]):
			continue
		items.append(
			BacklogItem(
				id=cells[0],
				item=cells[1],
				disposition=cells[2] if len(cells) > 2 else "",
				dossier_citation=cells[3] if len(cells) > 3 else "",
			)
		)
	return items


def parse_urs_by_backlog_item(path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
	"""Map backlog item id → URS IDs, plus URS ID → title.

	URS requirements are grouped under section headings that name their backlog item, e.g.
	`### 3.6 Characterisation-test harness (W0-6)`.
	"""
	by_item: dict[str, list[str]] = {}
	titles: dict[str, str] = {}
	current: list[str] = []
	for line in path.read_text(encoding="utf-8").splitlines():
		if SECTION_HEADING.match(line) and not URS_HEADING.match(line):
			# A heading naming no backlog item ends the previous grouping rather than
			# inheriting it — requirements would otherwise be credited to the wrong item.
			current = [
				item
				for match in SECTION_ITEMS.finditer(line)
				for item in re.findall(r"W\d+-\d+", match.group("items"))
			]
			for item_id in current:
				by_item.setdefault(item_id, [])
			continue
		heading = URS_HEADING.match(line)
		if heading:
			urs_id = heading.group("urs")
			titles[urs_id] = heading.group("title")
			for item_id in current:
				if urs_id not in by_item[item_id]:
					by_item[item_id].append(urs_id)
	return by_item, titles


def parse_traceability(path: Path) -> dict[str, list[str]]:
	"""Map URS ID → mapped TC IDs from the traceability matrix of a TST document.

	A matrix row may carry several URS/TC pairs side by side (the W2 matrix is laid out in two
	columns), so every cell that holds a URS ID is read with the cell following it.
	"""
	mapping: dict[str, list[str]] = {}
	for line in path.read_text(encoding="utf-8").splitlines():
		cells = split_table_row(line)
		for index, cell in enumerate(cells[:-1]):
			if not URS_ID.fullmatch(cell):
				continue
			tcs = TC_ID.findall(cells[index + 1])
			if tcs:
				mapping.setdefault(cell, [])
				for tc in tcs:
					if tc not in mapping[cell]:
						mapping[cell].append(tc)
	return mapping


def _tc_ids(text: str | None) -> tuple[str, ...]:
	if not text:
		return ()
	return tuple(dict.fromkeys(TC_ID.findall(text)))


def collect_test_evidence(tests_root: Path, repo_root: Path) -> list[EvidenceCitation]:
	"""Collect TC IDs cited by test docstrings under `tests_root`.

	A TC ID in a function/class docstring links that test. A TC ID cited only in the module
	docstring links the module as a whole. Nothing else counts as evidence — citation in the
	docstring is the traceability rule the programme mandates.
	"""
	evidence: list[EvidenceCitation] = []
	for path in sorted(tests_root.rglob("test_*.py")):
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"))
		except SyntaxError:
			continue
		relative = path.relative_to(repo_root).as_posix()
		function_level: list[EvidenceCitation] = []
		covered: set[str] = set()
		for node in ast.walk(tree):
			if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
				continue
			tcs = _tc_ids(ast.get_docstring(node))
			if tcs:
				function_level.append(EvidenceCitation(tcs, f"{relative}::{node.name}", "test"))
				covered.update(tcs)
		module_only = tuple(tc for tc in _tc_ids(ast.get_docstring(tree)) if tc not in covered)
		if module_only:
			evidence.append(EvidenceCitation(module_only, relative, "test"))
		evidence.extend(function_level)
	return evidence


def parse_manual_evidence(path: Path, repo_root: Path) -> list[EvidenceCitation]:
	"""Parse `docs/evidence/manual-evidence.md`: TC IDs verified outside the pytest suite.

	Some test cases cannot be a pytest (a red-then-green pipeline run, for example). They
	are recorded in that register with their citation and reported as *manual* evidence, so
	the pack never silently claims automated coverage.
	"""
	if not path.exists():
		return []
	entries: list[EvidenceCitation] = []
	relative = path.relative_to(repo_root).as_posix()
	for line in path.read_text(encoding="utf-8").splitlines():
		cells = split_table_row(line)
		if len(cells) < 2:
			continue
		tcs = _tc_ids(cells[0])
		if not tcs:
			continue
		citation = (cells[2] if len(cells) > 2 and cells[2] else cells[1]).replace("`", "")
		entries.append(EvidenceCitation(tcs, f"manual: {citation} (register: {relative})", "manual"))
	return entries
