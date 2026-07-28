"""Evidence-pack completeness — URS-W0-013 (AC-1), TC-W0-016 step 1.

The generator (`tools/evidence`, backlog item W0-7) must emit one row per W0 backlog item
with item → dossier citation → URS ID(s) → test ID(s) and zero unlinked items.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from tools.evidence.generate import main, output_path  # noqa: E402
from tools.evidence.model import build_report  # noqa: E402
from tools.evidence.render import render_markdown  # noqa: E402

W0_ITEMS = tuple(f"W0-{index}" for index in range(1, 9))


def mirror_repo(repo_root: Path, destination: Path) -> Path:
	"""Copy the inputs the generator reads, so a CLI run never writes into the working tree."""
	for relative in ("docs/waves", "docs/urs", "docs/test", "docs/evidence", "tests"):
		shutil.copytree(repo_root / relative, destination / relative)
	return destination


def test_report_has_one_row_per_backlog_item_with_the_full_chain(repo_root):
	"""URS-W0-013 AC-1 · TC-W0-016 step 1 — every W0 item is traced end to end."""
	report = build_report(repo_root, "W0")
	assert tuple(row.backlog.id for row in report.rows) == W0_ITEMS
	for row in report.rows:
		assert row.backlog.item, f"{row.backlog.id} has no item description"
		assert row.backlog.dossier_citation, f"{row.backlog.id} has no dossier citation"
		assert row.urs_ids, f"{row.backlog.id} has no URS link"
		assert row.tc_ids, f"{row.backlog.id} has no test-case link"
	assert report.unlinked == (), "no W0 backlog item may be unlinked"


def test_characterisation_harness_and_generator_items_are_fully_evidenced(repo_root):
	"""URS-W0-013 AC-1 · TC-W0-016 — W0-6 and W0-7 carry their own automated evidence."""
	report = build_report(repo_root, "W0")
	for backlog_id in ("W0-6", "W0-7"):
		row = report.row(backlog_id)
		assert row.missing_tc_ids == (), f"{backlog_id} missing evidence for {row.missing_tc_ids}"
		assert row.status == "complete"
		assert all(row.evidence[tc_id] for tc_id in row.tc_ids)


def test_cli_writes_the_pack_and_exits_zero_without_unlinked_items(repo_root, tmp_path, capsys):
	"""URS-W0-013 AC-1 · TC-W0-016 step 1 — the CLI is the audit entrypoint."""
	mirror = mirror_repo(repo_root, tmp_path / "repo")
	exit_code = main(["--wave", "W0", "--repo-root", str(mirror)])
	captured = capsys.readouterr()
	assert exit_code == 0, f"a W0 backlog item is unlinked: {captured.err}"
	assert "8 backlog items" in captured.out
	assert "UNLINKED" not in captured.err
	assert output_path(mirror, "W0").exists()


def test_committed_pack_lists_every_backlog_item(repo_root):
	"""URS-W0-013 AC-1 · TC-W0-016 — the committed markdown carries the traceability table."""
	pack = output_path(repo_root, "W0")
	assert pack.exists(), "the generated W0 evidence pack must be committed"
	content = pack.read_text(encoding="utf-8")
	assert "| # | Item | Disposition | Dossier finding (evidence) | URS | Test cases | Status |" in content
	for backlog_id in W0_ITEMS:
		assert f"| {backlog_id} |" in content, f"{backlog_id} is missing from the committed pack"


def test_rendered_report_is_deterministic(repo_root):
	"""URS-W0-013 · TC-W0-016 — regenerating from unchanged inputs is byte-identical."""
	assert render_markdown(build_report(repo_root, "W0")) == render_markdown(build_report(repo_root, "W0"))
