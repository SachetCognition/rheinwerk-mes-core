"""CLI for the wave-exit evidence-pack generator (W0-7, URS-W0-013).

	python -m tools.evidence.generate --wave W0                 # write docs/evidence/W0-evidence-pack.md
	python -m tools.evidence.generate --wave W0 --check         # verify the committed pack is current
	python -m tools.evidence.generate --wave W0 --strict        # also fail on evidence-incomplete items
	python -m tools.evidence.generate --wave W0 --html          # additionally render docs/html/W0-evidence-pack.html

Exit codes: `0` success, `1` at least one backlog item is unlinked (audit spine broken) or
`--strict`/`--check` was violated.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .model import build_report
from .render import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]


def output_path(repo_root: Path, wave: str) -> Path:
	return repo_root / "docs" / "evidence" / f"{wave}-evidence-pack.md"


def _render_html(repo_root: Path, markdown_path: Path, wave: str) -> None:
	html_path = repo_root / "docs" / "html" / f"{wave}-evidence-pack.html"
	html_path.parent.mkdir(parents=True, exist_ok=True)
	subprocess.run(  # noqa: S603
		[
			sys.executable,
			str(repo_root / "tools" / "htmlgen" / "htmlgen.py"),
			str(markdown_path),
			str(html_path),
			f"Wave {wave} — evidence pack",
			"Rheinwerk Chemie GmbH — MES consolidation",
		],
		check=True,
		cwd=repo_root,
	)


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(prog="python -m tools.evidence.generate")
	parser.add_argument("--wave", required=True, help="wave identifier, e.g. W0")
	parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="repository root")
	parser.add_argument(
		"--check",
		action="store_true",
		help="do not write; fail when the committed pack differs from the generated one",
	)
	parser.add_argument(
		"--strict",
		action="store_true",
		help="also exit non-zero when any backlog item is evidence-incomplete",
	)
	parser.add_argument("--html", action="store_true", help="also render the standalone HTML artefact")
	args = parser.parse_args(argv)

	wave = args.wave.upper()
	repo_root = args.repo_root.resolve()
	report = build_report(repo_root, wave)
	markdown = render_markdown(report)
	destination = output_path(repo_root, wave)

	if args.check:
		current = destination.read_text(encoding="utf-8") if destination.exists() else ""
		if current != markdown:
			print(
				f"{destination.relative_to(repo_root)} is out of date — "
				f"run: python -m tools.evidence.generate --wave {wave}",
				file=sys.stderr,
			)
			return 1
	else:
		destination.parent.mkdir(parents=True, exist_ok=True)
		destination.write_text(markdown, encoding="utf-8")
		print(f"wrote {destination.relative_to(repo_root)}")
		if args.html:
			_render_html(repo_root, destination, wave)

	print(
		f"wave {wave}: {len(report.rows)} backlog items — "
		f"{len(report.complete)} complete, {len(report.incomplete)} evidence-incomplete, "
		f"{len(report.unlinked)} unlinked"
	)
	for row in report.incomplete:
		print(f"  evidence-incomplete: {row.backlog.id} — {'; '.join(row.notes)}")
	for row in report.unlinked:
		print(f"  UNLINKED: {row.backlog.id} — {'; '.join(row.notes)}", file=sys.stderr)

	if report.unlinked:
		return 1
	if args.strict and report.incomplete:
		print("--strict: evidence-incomplete backlog items present", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
