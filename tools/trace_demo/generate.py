"""CLI for the W2 trace demonstration (W2-9, URS-W2-028).

	FRAPPE_SITE=dev.localhost python -m tools.trace_demo.generate            # write the artefact
	FRAPPE_SITE=dev.localhost python -m tools.trace_demo.generate --check    # verify it is current

Needs a connected site (the trace reads the fixture genealogy), so unlike the evidence pack
this generator is run against the running stack, and its output is committed as the
wave-acceptance artefact `docs/evidence/W2-trace-demo.md`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def output_path(repo_root: Path) -> Path:
	return repo_root / "docs" / "evidence" / "W2-trace-demo.md"


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(prog="python -m tools.trace_demo.generate")
	parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
	parser.add_argument("--bench-path", type=Path, default=Path.home() / "frappe-bench")
	parser.add_argument("--site", default=os.environ.get("FRAPPE_SITE", "dev.localhost"))
	parser.add_argument("--check", action="store_true", help="do not write; fail when stale")
	args = parser.parse_args(argv)

	import frappe

	sites_path = args.bench_path / "sites"
	os.chdir(sites_path)
	frappe.init(site=args.site, sites_path=str(sites_path))
	frappe.connect()
	try:
		from tools.trace_demo import demo

		markdown = demo.render_markdown(demo.run())
	finally:
		frappe.db.rollback()
		frappe.destroy()

	target = output_path(args.repo_root)
	if args.check:
		if not target.exists() or target.read_text(encoding="utf-8") != markdown:
			print(f"{target.relative_to(args.repo_root)} is stale — regenerate it", file=sys.stderr)
			return 1
		print(f"{target.relative_to(args.repo_root)} is current")
		return 0

	target.write_text(markdown, encoding="utf-8")
	print(f"wrote {target.relative_to(args.repo_root)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
