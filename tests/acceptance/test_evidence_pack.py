"""TC-W0-016 — Wave-exit evidence pack completeness (verifies URS-W0-013).

AC-1: the generator emits one row per W0 backlog item (W0-1…W0-8) linking
      item → dossier citation → URS ID(s) → test ID(s), with zero unlinked items.
AC-2: a backlog item stripped of its test link is flagged evidence-incomplete
      rather than omitted.
"""

import re
from pathlib import Path

import evidence_pack

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKLOG = REPO_ROOT / "docs" / "waves" / "W0-foundation.md"
URS = REPO_ROOT / "docs" / "urs" / "URS-W0-foundation.md"
TST = REPO_ROOT / "docs" / "test" / "TST-W0-foundation.md"

EXPECTED_ITEMS = [f"W0-{n}" for n in range(1, 9)]


def _texts():
    return (
        BACKLOG.read_text(encoding="utf-8"),
        URS.read_text(encoding="utf-8"),
        TST.read_text(encoding="utf-8"),
    )


def test_ac1_one_row_per_item_fully_linked():
    backlog_text, urs_text, tst_text = _texts()
    evidence = evidence_pack.build_evidence(backlog_text, urs_text, tst_text, "W0")

    assert [i.item_id for i in evidence.items] == EXPECTED_ITEMS

    for item in evidence.items:
        assert item.dossier_finding, f"{item.item_id} missing dossier citation"
        assert item.urs_ids, f"{item.item_id} has no URS link"
        assert item.test_ids, f"{item.item_id} has no test link"
        assert item.complete
        assert item.status == evidence_pack.STATUS_COMPLETE

    assert evidence.incomplete == []


def test_ac1_report_renders_full_matrix():
    backlog_text, urs_text, tst_text = _texts()
    evidence = evidence_pack.build_evidence(backlog_text, urs_text, tst_text, "W0")
    report = evidence_pack.render_markdown(
        evidence, {"backlog": "b", "urs": "u", "tst": "t"}
    )

    assert "Evidence-incomplete: 0" in report
    for item in evidence.items:
        assert item.item_id in report
        for urs_id in item.urs_ids:
            assert urs_id in report
        for test_id in item.test_ids:
            assert test_id in report


def test_ac2_stripped_test_link_flagged_not_omitted():
    backlog_text, urs_text, tst_text = _texts()

    # Fixture: strip W0-7's test link (URS-W0-013 → TC-W0-016) from the matrix.
    stripped_tst = re.sub(
        r"(?m)^\| URS-W0-013 \|[^|]*\|",
        "| URS-W0-013 |  |",
        tst_text,
    )
    assert stripped_tst != tst_text

    evidence = evidence_pack.build_evidence(backlog_text, urs_text, stripped_tst, "W0")
    by_id = {i.item_id: i for i in evidence.items}

    w0_7 = by_id["W0-7"]
    assert w0_7.urs_ids == ["URS-W0-013"]  # URS link intact
    assert w0_7.test_ids == []  # test link stripped
    assert not w0_7.complete
    assert w0_7.status.startswith(evidence_pack.STATUS_INCOMPLETE)
    assert "test link" in w0_7.status

    # Not omitted: still one row per backlog item.
    assert [i.item_id for i in evidence.items] == EXPECTED_ITEMS

    report = evidence_pack.render_markdown(
        evidence, {"backlog": "b", "urs": "u", "tst": "t"}
    )
    assert "W0-7" in report
    assert evidence_pack.STATUS_INCOMPLETE in report
    assert "Evidence-incomplete: 1" in report
