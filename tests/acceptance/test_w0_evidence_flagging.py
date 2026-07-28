"""Evidence-pack flagging and audit-spine enforcement — URS-W0-013 (AC-2), TC-W0-016 step 2.

An item stripped of its test link must be **flagged evidence-incomplete, not omitted**, and
a backlog item with no URS→TC link at all must make the generator exit non-zero.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from tools.evidence.generate import main, output_path  # noqa: E402
from tools.evidence.model import (  # noqa: E402
	STATUS_COMPLETE,
	STATUS_INCOMPLETE,
	STATUS_UNLINKED,
	build_report,
)
from tools.evidence.parsers import EvidenceCitation, collect_test_evidence  # noqa: E402
from tools.evidence.render import render_markdown  # noqa: E402


def _mirror_repo(repo_root: Path, destination: Path) -> Path:
	for relative in ("docs/waves", "docs/urs", "docs/test", "docs/evidence", "tests"):
		shutil.copytree(repo_root / relative, destination / relative)
	return destination


def _index(entries: list[EvidenceCitation]) -> dict[str, list[EvidenceCitation]]:
	index: dict[str, list[EvidenceCitation]] = {}
	for entry in entries:
		for tc_id in entry.tc_ids:
			index.setdefault(tc_id, []).append(entry)
	return index


def test_stripping_a_test_link_flags_the_item_instead_of_omitting_it(repo_root):
	"""URS-W0-013 AC-2 · TC-W0-016 step 2 — evidence-incomplete items stay in the report."""
	entries = collect_test_evidence(repo_root / "tests", repo_root)
	full = _index(entries)
	assert build_report(repo_root, "W0", evidence_index=full).row("W0-6").status == STATUS_COMPLETE

	stripped = {tc_id: list(locations) for tc_id, locations in full.items() if tc_id != "TC-W0-014"}
	report = build_report(repo_root, "W0", evidence_index=stripped)
	row = report.row("W0-6")

	assert row.status == STATUS_INCOMPLETE
	assert "TC-W0-014" in row.missing_tc_ids
	assert row in report.incomplete
	assert "W0-6" in {item.backlog.id for item in report.rows}, "the item must never be omitted"

	markdown = render_markdown(report)
	assert "| W0-6 |" in markdown
	assert "**evidence-incomplete**" in markdown
	assert "no test cites TC-W0-014" in markdown


def test_unlinked_backlog_item_makes_the_generator_exit_non_zero(repo_root, tmp_path, capsys):
	"""URS-W0-013 AC-1 · TC-W0-016 — zero unlinked items is enforced, not merely reported."""
	mirror = _mirror_repo(repo_root, tmp_path / "repo")
	backlog = next((mirror / "docs" / "waves").glob("W0-*.md"))
	backlog.write_text(
		backlog.read_text(encoding="utf-8") + "| W0-9 | Orphan item with no requirement | — | — |\n",
		encoding="utf-8",
	)

	report = build_report(mirror, "W0")
	assert report.row("W0-9").status == STATUS_UNLINKED

	exit_code = main(["--wave", "W0", "--repo-root", str(mirror)])
	captured = capsys.readouterr()
	assert exit_code == 1
	assert "UNLINKED: W0-9" in captured.err
	assert "| W0-9 |" in output_path(mirror, "W0").read_text(encoding="utf-8")


def test_strict_mode_fails_on_evidence_incomplete_items(repo_root, tmp_path, capsys):
	"""URS-W0-013 AC-2 · TC-W0-016 — `--strict` is the wave-exit gate for open evidence."""
	mirror = _mirror_repo(repo_root, tmp_path / "repo")
	for path in (mirror / "tests").rglob("test_w0_scaffold.py"):
		path.unlink()
	(mirror / "docs" / "evidence" / "manual-evidence.md").unlink(missing_ok=True)

	assert main(["--wave", "W0", "--repo-root", str(mirror)]) == 0
	assert main(["--wave", "W0", "--repo-root", str(mirror), "--strict"]) == 1
	captured = capsys.readouterr()
	assert "evidence-incomplete: W0-1" in captured.out


def test_check_mode_detects_a_stale_committed_pack(repo_root, tmp_path, capsys):
	"""URS-W0-013 · TC-W0-016 — `--check` proves a committed pack matches the specs."""
	mirror = _mirror_repo(repo_root, tmp_path / "repo")
	assert main(["--wave", "W0", "--repo-root", str(mirror)]) == 0
	assert main(["--wave", "W0", "--repo-root", str(mirror), "--check"]) == 0

	output_path(mirror, "W0").write_text("stale\n", encoding="utf-8")
	assert main(["--wave", "W0", "--repo-root", str(mirror), "--check"]) == 1
	assert "out of date" in capsys.readouterr().err


def test_manual_evidence_is_reported_as_manual(repo_root):
	"""URS-W0-013 · TC-W0-016 — evidence verified outside pytest is never silently automated."""
	report = build_report(repo_root, "W0")
	row = report.row("W0-1")
	assert "TC-W0-003" in row.tc_ids
	assert any("manual evidence" in note for note in row.notes), (
		"TC-W0-003 (pipeline behaviour) must be reported as manual evidence"
	)
