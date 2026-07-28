"""Expiry divergence and the generated per-gate behaviour record (W1-9/W1-10).

URS-W1-030 (AC-2/AC-3) · TC-W1-033 and URS-W1-031 · TC-W1-034. Offline: the record is
derived from contract execution and docstring citations, so no site is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT, REPO_ROOT / "tests"):
	if str(path) not in sys.path:
		sys.path.insert(0, str(path))

from characterisation.api import ENTRYPOINTS, Verdict  # noqa: E402
from characterisation.registry import Contract, Divergence, get  # noqa: E402

from tools.behaviour import model  # noqa: E402
from tools.behaviour.generate import main, output_path  # noqa: E402
from tools.behaviour.render import render_markdown  # noqa: E402

SIGNED_RECORD = "docs/decisions/DEC-W1-030-expiry-policy.md"


def _expiry_gate() -> model.Gate:
	return next(gate for gate in model.W1_GATES if gate.contract_id == "CHAR-EXPIRY-ISSUE-01")


def test_expiry_delta_is_reported_as_intentional_divergence(repo_root: Path):
	"""URS-W1-030 AC-2 · TC-W1-033 step 1 — the legacy contract's delta is a divergence.

	`CHAR-EXPIRY-ISSUE-01` encodes Plant A's FEFO-advisory verdict (an expired resource is
	issuable). The target refuses it, so the contract *must* show a delta — and the record
	must classify that delta as a signed-off divergence rather than a parity failure.
	"""
	contract = get("CHAR-EXPIRY-ISSUE-01")
	assert contract.divergence is not None
	assert contract.resolution().is_target_implementation, "the divergence must be measured against W1 code"

	verdict = model.contract_verdict(repo_root, _expiry_gate(), contract)

	assert verdict.verdict == model.VERDICT_DIVERGENCE
	assert verdict.decision == "URS-W1-030"
	assert verdict.sign_off, "the divergence row links the business sign-off"


def test_generation_fails_without_the_sign_off_identifier(repo_root: Path, tmp_path: Path):
	"""URS-W1-030 AC-3 · TC-W1-033 steps 2+3 — no sign-off, no record; restored, it passes."""
	contract = get("CHAR-EXPIRY-ISSUE-01")
	signed = (repo_root / SIGNED_RECORD).read_text(encoding="utf-8")
	unsigned = signed.replace(
		"- **Sign-off:** Sachet Agarwal — Programme Owner — 28.07.2026",
		"- **Sign-off:** PENDING",
	)
	assert unsigned != signed, "the committed decision record must carry a sign-off line"
	(tmp_path / "docs" / "decisions").mkdir(parents=True)
	record_path = tmp_path / SIGNED_RECORD
	record_path.write_text(unsigned, encoding="utf-8")

	assert model.sign_off_of(tmp_path, SIGNED_RECORD) is None
	with pytest.raises(model.RecordError, match="no business sign-off"):
		model.contract_verdict(tmp_path, _expiry_gate(), contract)

	record_path.write_text(signed, encoding="utf-8")
	restored = model.contract_verdict(tmp_path, _expiry_gate(), contract)
	assert restored.verdict == model.VERDICT_DIVERGENCE
	assert restored.sign_off == "Sachet Agarwal — Programme Owner — 28.07.2026"


def test_record_has_one_row_per_gate_with_its_legacy_citation(repo_root: Path):
	"""URS-W1-031 AC-1/AC-2 · TC-W1-034 steps 1+2 — ten gates, one divergence, citations."""
	verdicts = model.build_record(repo_root)

	assert len(verdicts) == 10, "URS-W1-031 enumerates ten W1 gates"
	assert all(verdict.gate.legacy_source for verdict in verdicts)
	divergences = [verdict for verdict in verdicts if verdict.verdict == model.VERDICT_DIVERGENCE]
	assert [verdict.gate.urs_ids for verdict in divergences] == [("URS-W1-013", "URS-W1-030")]
	assert all(verdict.sign_off is None for verdict in verdicts if verdict not in divergences), (
		"only a signed-off divergence carries a sign-off reference"
	)

	markdown = render_markdown("W1", verdicts)
	assert markdown == (repo_root / "docs" / "evidence" / "W1-behaviour-record.md").read_text(
		encoding="utf-8"
	), "the committed record is stale — regenerate with python -m tools.behaviour.generate --wave W1"


def test_generation_fails_when_a_contract_breaks_without_a_divergence(
	repo_root: Path, monkeypatch: pytest.MonkeyPatch
):
	"""URS-W1-031 AC-3 · TC-W1-034 step 3 — unrecorded drift aborts generation."""
	monkeypatch.setitem(ENTRYPOINTS, "broken_concern", "rheinwerk_mes.does.not.exist")
	drifted = Contract(
		id="CHAR-DRIFT-01",
		title="a rule whose target verdict no longer matches the fixture",
		concern="broken_concern",
		legacy_source="ResourceManagementServiceImpl.java:1015-1027",
		fixture="expiry_issue.json",
		fallback=lambda issue: Verdict(allowed=False, errors=("drift",)),
		checker=get("CHAR-EXPIRY-ISSUE-01").checker,
		urs_ids=("URS-W1-031",),
		tc_ids=("TC-W1-034",),
	)
	gate = model.Gate(
		name="drifted gate",
		urs_ids=("URS-W1-031",),
		legacy_source="ResourceManagementServiceImpl.java:1015-1027",
		contract_id="CHAR-DRIFT-01",
	)

	with pytest.raises(model.RecordError, match="without a recorded divergence"):
		model.contract_verdict(repo_root, gate, drifted)


def test_declared_divergence_that_stopped_diverging_aborts_generation(
	repo_root: Path, monkeypatch: pytest.MonkeyPatch
):
	"""URS-W1-031 AC-3 — a divergence row may not claim a delta that no longer exists."""
	contract = get("CHAR-EXPIRY-ISSUE-01")
	monkeypatch.setitem(ENTRYPOINTS, "compliant_concern", "rheinwerk_mes.does.not.exist")
	compliant = Contract(
		id="CHAR-EXPIRY-COMPLIANT-01",
		title="the same divergence, but the target went back to the legacy verdict",
		concern="compliant_concern",
		legacy_source=contract.legacy_source,
		fixture=contract.fixture,
		fallback=lambda issue: Verdict(allowed=True),
		checker=contract.checker,
		urs_ids=contract.urs_ids,
		tc_ids=contract.tc_ids,
		divergence=Divergence(
			decision="URS-W1-030",
			record=SIGNED_RECORD,
			summary="declared but no longer observable",
		),
	)
	# The resolved implementation matches the fixture, so the flagged case passes — an error.
	with pytest.raises(model.RecordError, match="no longer shows a delta"):
		model.contract_verdict(repo_root, _expiry_gate(), compliant)


def test_cli_check_mode_reports_the_committed_record_as_current(repo_root: Path, capsys):
	"""URS-W1-031 · TC-W1-034 — `--check` is the CI gate on a stale record."""
	assert main(["--wave", "W1", "--repo-root", str(repo_root), "--check"]) == 0
	assert "is current" in capsys.readouterr().out
	assert output_path(repo_root, "W1").exists()
