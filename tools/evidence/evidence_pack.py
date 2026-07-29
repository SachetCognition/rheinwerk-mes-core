#!/usr/bin/env python3
"""Wave-exit evidence-pack generator (URS-W0-013 / W0-7).

Links every backlog item of a wave to its dossier finding and to the URS
requirements and test cases that implement and verify it, so a business viewer
can audit wave exit without reading source code.

The report is derived from the programme record copies (single source of truth,
no duplicated manifest that could drift):

- backlog item + dossier finding : ``docs/waves/<wave>-*.md`` (backlog table)
- backlog item -> URS ID(s)       : ``docs/urs/URS-<wave>-*.md`` (``(W0-N)`` section tags)
- URS ID -> test ID(s)            : ``docs/test/TST-<wave>-*.md`` (traceability matrix)

Audit spine: backlog item -> dossier finding -> URS requirement(s) -> test case(s).

Usage:
    evidence_pack.py --wave W0 \
        --backlog docs/waves/W0-foundation.md \
        --urs docs/urs/URS-W0-foundation.md \
        --tst docs/test/TST-W0-foundation.md \
        --out docs/evidence/EVIDENCE-W0-foundation.md
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

STATUS_COMPLETE = "COMPLETE"
STATUS_INCOMPLETE = "EVIDENCE-INCOMPLETE"


@dataclass
class BacklogItem:
    """One wave backlog item with its resolved evidence links."""

    item_id: str
    description: str
    disposition: str
    dossier_finding: str
    urs_ids: list[str] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        gaps = []
        if not self.urs_ids:
            gaps.append("URS link")
        if not self.test_ids:
            gaps.append("test link")
        return gaps

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def status(self) -> str:
        if self.complete:
            return STATUS_COMPLETE
        return f"{STATUS_INCOMPLETE} (no {', '.join(self.missing)})"


@dataclass
class WaveEvidence:
    """The resolved evidence spine for a wave."""

    wave: str
    items: list[BacklogItem]

    @property
    def incomplete(self) -> list[BacklogItem]:
        return [i for i in self.items if not i.complete]


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row into trimmed cells."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_backlog(text: str, wave: str) -> list[BacklogItem]:
    """Parse the wave backlog table into ordered backlog items.

    Table columns: ``#`` | ``Item`` | ``Disposition / golden source`` |
    ``Dossier finding (evidence)``.
    """
    item_re = re.compile(rf"^{re.escape(wave)}-\d+$")
    items: list[BacklogItem] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 4 or not item_re.match(cells[0]):
            continue
        items.append(
            BacklogItem(
                item_id=cells[0],
                description=cells[1],
                disposition=cells[2],
                dossier_finding=cells[3],
            )
        )
    return items


def parse_urs_to_backlog(text: str, wave: str) -> dict[str, str]:
    """Map each URS ID to its backlog item via ``### x.y ... (W0-N)`` section tags.

    URS requirements outside a tagged section (e.g. the non-functional floor) are
    intentionally not mapped to a backlog item and are excluded from the report.
    """
    section_re = re.compile(rf"^#{{2,3}}\s+.*\(({re.escape(wave)}-\d+)\)\s*$")
    urs_re = re.compile(rf"^#{{3,4}}\s+(URS-{re.escape(wave)}-\d+)\b")
    mapping: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        section = section_re.match(line.strip())
        if section:
            current = section.group(1)
            continue
        if re.match(r"^#{2,3}\s", line) and not section:
            # A new untagged section (e.g. "## 4. Non-functional requirements")
            # ends the scope of the previous backlog item.
            current = None
        urs = urs_re.match(line.strip())
        if urs and current:
            mapping[urs.group(1)] = current
    return mapping


def parse_traceability(text: str, wave: str) -> dict[str, list[str]]:
    """Parse the TST traceability matrix into ``URS ID -> [test IDs]``.

    Reads the forward (URS -> test cases) side of the matrix; the reverse side is
    ignored. Rows without test cases keep an empty list.
    """
    urs_cell_re = re.compile(rf"^(URS-{re.escape(wave)}-\d+)$")
    tc_re = re.compile(rf"TC-{re.escape(wave)}-\d+")
    mapping: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 2 or not urs_cell_re.match(cells[0]):
            continue
        mapping[cells[0]] = tc_re.findall(cells[1])
    return mapping


def build_evidence(
    backlog_text: str, urs_text: str, tst_text: str, wave: str
) -> WaveEvidence:
    """Cross-link backlog, URS and test sources into the wave evidence spine."""
    items = parse_backlog(backlog_text, wave)
    urs_to_backlog = parse_urs_to_backlog(urs_text, wave)
    urs_to_tests = parse_traceability(tst_text, wave)

    by_item: dict[str, list[str]] = {i.item_id: [] for i in items}
    for urs_id, item_id in urs_to_backlog.items():
        if item_id in by_item:
            by_item[item_id].append(urs_id)

    for item in items:
        item.urs_ids = sorted(by_item[item.item_id])
        tests: list[str] = []
        for urs_id in item.urs_ids:
            for tc in urs_to_tests.get(urs_id, []):
                if tc not in tests:
                    tests.append(tc)
        item.test_ids = sorted(tests)

    return WaveEvidence(wave=wave, items=items)


def render_markdown(evidence: WaveEvidence, sources: dict[str, str]) -> str:
    """Render the evidence pack as a Markdown report."""
    total = len(evidence.items)
    incomplete = evidence.incomplete
    complete = total - len(incomplete)

    lines: list[str] = []
    lines.append(f"# Wave-exit evidence pack — {evidence.wave}")
    lines.append("")
    lines.append(
        "Auto-generated by `tools/evidence/evidence_pack.py` from the programme "
        "record copies (do not edit by hand):"
    )
    lines.append("")
    lines.append(f"- Backlog: `{sources['backlog']}`")
    lines.append(f"- URS: `{sources['urs']}`")
    lines.append(f"- Tests: `{sources['tst']}`")
    lines.append("")
    lines.append(
        "Audit spine: backlog item → dossier finding → URS requirement(s) → "
        "test case(s)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Backlog items: {total}")
    lines.append(f"- Fully linked: {complete}")
    lines.append(f"- Evidence-incomplete: {len(incomplete)}")
    if incomplete:
        flagged = ", ".join(f"{i.item_id} ({', '.join(i.missing)})" for i in incomplete)
        lines.append(f"- Flagged: {flagged}")
    lines.append("")
    lines.append("## Evidence matrix")
    lines.append("")
    lines.append(
        "| Item | Description | Disposition | Dossier finding | URS ID(s) | "
        "Test ID(s) | Status |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for item in evidence.items:
        lines.append(
            "| {id} | {desc} | {disp} | {dossier} | {urs} | {tests} | {status} |".format(
                id=item.item_id,
                desc=item.description,
                disp=item.disposition,
                dossier=item.dossier_finding,
                urs=", ".join(item.urs_ids) or "—",
                tests=", ".join(item.test_ids) or "—",
                status=item.status,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _default_sources(wave: str) -> dict[str, str]:
    slug = {
        "W0": "foundation",
        "W1": "production-core",
        "W2": "traceability-quality",
        "W3": "planning-boundary",
        "W4": "cutover-decommission",
    }.get(wave, wave.lower())
    return {
        "backlog": f"docs/waves/{wave}-{slug}.md",
        "urs": f"docs/urs/URS-{wave}-{slug}.md",
        "tst": f"docs/test/TST-{wave}-{slug}.md",
        "out": f"docs/evidence/EVIDENCE-{wave}-{slug}.md",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    defaults = _default_sources("W0")
    p = argparse.ArgumentParser(description="Wave-exit evidence-pack generator")
    p.add_argument("--wave", default="W0", help="Wave identifier (e.g. W0)")
    p.add_argument("--backlog", help="Path to the wave backlog markdown")
    p.add_argument("--urs", help="Path to the URS markdown")
    p.add_argument("--tst", help="Path to the test/verification markdown")
    p.add_argument("--out", help="Path to write the evidence report (default: stdout)")
    p.add_argument(
        "--fail-on-incomplete",
        action="store_true",
        help="Exit non-zero if any backlog item is evidence-incomplete",
    )
    args = p.parse_args(argv)
    d = _default_sources(args.wave)
    args.backlog = args.backlog or d["backlog"]
    args.urs = args.urs or d["urs"]
    args.tst = args.tst or d["tst"]
    if args.out is None and argv is None and args.wave == "W0":
        args.out = defaults["out"]
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = build_evidence(
        Path(args.backlog).read_text(encoding="utf-8"),
        Path(args.urs).read_text(encoding="utf-8"),
        Path(args.tst).read_text(encoding="utf-8"),
        args.wave,
    )
    report = render_markdown(
        evidence,
        {"backlog": args.backlog, "urs": args.urs, "tst": args.tst},
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        flagged = len(evidence.incomplete)
        print(
            f"wrote {out} ({len(evidence.items)} items, {flagged} evidence-incomplete)"
        )
    else:
        print(report)
    if args.fail_on_incomplete and evidence.incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
