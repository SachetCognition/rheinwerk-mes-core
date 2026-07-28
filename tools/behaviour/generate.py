"""CLI for the per-gate behaviour record (W1-10, URS-W1-031).

	python -m tools.behaviour.generate --wave W1            # write docs/evidence/W1-behaviour-record.md
	python -m tools.behaviour.generate --wave W1 --check    # verify the committed record is current

Exit codes: `0` success, `1` generation aborted (a contract failed without a signed-off
divergence, a divergence lacks its business sign-off, or an adopted gate has no verifying
test) or `--check` found the committed record stale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import RecordError, build_record
from .render import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]


def output_path(repo_root: Path, wave: str) -> Path:
	return repo_root / "docs" / "evidence" / f"{wave}-behaviour-record.md"


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(prog="python -m tools.behaviour.generate")
	parser.add_argument("--wave", required=True, help="wave identifier, e.g. W1")
	parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="repository root")
	parser.add_argument(
		"--check",
		action="store_true",
		help="do not write; fail when the committed record differs from the generated one",
	)
	args = parser.parse_args(argv)

	try:
		verdicts = build_record(args.repo_root)
	except RecordError as error:
		print(f"behaviour record generation failed: {error}", file=sys.stderr)
		return 1

	markdown = render_markdown(args.wave, verdicts)
	path = output_path(args.repo_root, args.wave)
	if args.check:
		current = path.read_text(encoding="utf-8") if path.exists() else ""
		if current != markdown:
			print(f"{path.relative_to(args.repo_root)} is stale — regenerate it", file=sys.stderr)
			return 1
		print(f"{path.relative_to(args.repo_root)} is current")
		return 0

	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(markdown, encoding="utf-8")
	print(f"wrote {path.relative_to(args.repo_root)}")
	divergences = [verdict for verdict in verdicts if verdict.sign_off]
	print(f"wave {args.wave}: {len(verdicts)} gates, {len(divergences)} signed-off divergence(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
