"""W2-10 — the e-signature decision record is complete and signed off.

TC-W2-037 (URS-W2-029 AC-1, AC-2): the committed record lists the e-signature requirement per
governed transition — at minimum Blocked⇄Released, CoA issue and recipe Accept — names the
sign-off authority and date, and, because it requires signatures for some transitions,
documents and schedules the enforcement-point design.

Offline test: the record is repository evidence, so no site is needed.
"""

from __future__ import annotations

import re

import pytest

RECORD = "docs/decisions/DEC-W2-029-e-signature-policy.md"

#: URS-W2-029 AC-1 — the transitions the record must decide explicitly.
REQUIRED_TRANSITIONS = (
	"Quarantined → **Released**",
	"→ **Blocked**",
	"Blocked → **Released**",
	"**CoA issue**",
	"Checked → **Accepted**",
)

SIGN_OFF = re.compile(
	r"^- \*\*Sign-off:\*\* (?P<name>.+?) — (?P<role>.+?) — (?P<date>\d{2}\.\d{2}\.\d{4})$", re.M
)


@pytest.fixture(scope="module")
def record(repo_root) -> str:
	path = repo_root / RECORD
	assert path.exists(), f"{RECORD} missing — EXIT-W2-5 cannot pass without the decision record"
	return path.read_text(encoding="utf-8")


def test_tc_w2_037_record_decides_every_compliance_critical_transition(record):
	"""TC-W2-037 step 1 (URS-W2-029 AC-1) — per-transition requirement is stated."""
	for transition in REQUIRED_TRANSITIONS:
		assert transition in record, f"{transition} is not decided in {RECORD}"
	assert "Audit trail" in record, "the record must also name the transitions that stay audit-only"


def test_tc_w2_037_record_names_a_sign_off_authority_and_date(record):
	"""TC-W2-037 step 1 (URS-W2-029 AC-1) — a named human accepted the policy.

	A `PENDING` sign-off fails here exactly as the W1 expiry record does, so EXIT-W2-5 cannot
	be ticked on an unsigned decision.
	"""
	match = SIGN_OFF.search(record)
	assert match, "no `- **Sign-off:** name — role — DD.MM.YYYY` line found"
	assert match.group("name").strip() and "PENDING" not in match.group("name")
	assert match.group("role").strip()


def test_tc_w2_037_enforcement_point_design_is_documented_and_scheduled(record):
	"""TC-W2-037 step 2 (URS-W2-029 AC-2) — signatures are required, so the hook is designed."""
	assert "## Enforcement-point design" in record
	for expected in ("rheinwerk_qa_state_gates", "Electronic Signature", "payload_hash", "W3"):
		assert expected in record, f"enforcement design does not state {expected}"
