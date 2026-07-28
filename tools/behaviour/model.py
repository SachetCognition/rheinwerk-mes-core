"""Per-gate parity/divergence record, derived from harness results (URS-W1-031).

The record is *generated*, never hand-maintained: for every gate the wave delivers, the
verdict comes from actually executing the gate's parity contract over its committed
fixtures, or — where the behaviour is adopted from the substrate and has no Qcadoo baseline
— from the test suite citing the gate's mapped test case. Consequences:

* a contract that starts failing without a recorded divergence aborts generation, so a
  silent behavioural drift cannot reach the evidence pack (URS-W1-031 AC-3);
* a divergence only counts once its decision record carries a sign-off (name/role/date),
  which is what makes EXIT-W1-5 a real gate (URS-W1-030 AC-3).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from tools.evidence.parsers import collect_test_evidence

#: `- **Sign-off:** Name — Role — DD.MM.YYYY` in a decision record.
SIGN_OFF = re.compile(r"^-\s+\*\*Sign-off:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE)

#: Sign-off values that do not count as signed.
UNSIGNED = {"", "pending", "tbd", "offen", "none", "—", "-"}

VERDICT_PARITY = "Parity"
VERDICT_DIVERGENCE = "Divergence"

#: Verdict source: a contract that ran, or a test that verifies an adopted behaviour.
SOURCE_CONTRACT = "contract"
SOURCE_ANCHOR = "anchor-adopt"


class RecordError(RuntimeError):
	"""Generation aborted — the record would have claimed something untrue."""


@dataclass(frozen=True)
class Gate:
	"""One gate the wave delivers, and how its verdict is established."""

	name: str
	urs_ids: tuple[str, ...]
	legacy_source: str
	#: Contract whose execution decides the verdict, else `None` for adopted behaviour.
	contract_id: str | None = None
	#: Test case proving an adopted behaviour (used when `contract_id` is `None`).
	tc_id: str | None = None


@dataclass(frozen=True)
class GateVerdict:
	"""Generated verdict for one gate."""

	gate: Gate
	verdict: str
	source: str
	detail: str
	sign_off: str | None = None
	decision: str | None = None


#: The ten W1 gates URS-W1-031 requires a row for, in the order the URS lists them.
W1_GATES: tuple[Gate, ...] = (
	Gate(
		name="Acceptance gate (dates, line, recipe reference)",
		urs_ids=("URS-W1-005",),
		legacy_source="OrderStateValidationService.java:44-47; OrderStateService.java:47-59",
		contract_id="CHAR-ORDER-ACCEPT-01",
	),
	Gate(
		name="Recipe-Accepted gate",
		urs_ids=("URS-W1-006",),
		legacy_source="TechnologyState.java:33-66 (Accepted recipes only); CDM-04",
		contract_id="CHAR-TECH-VALIDATE-01",
	),
	Gate(
		name="Completion gate (recorded output, execution dates)",
		urs_ids=("URS-W1-007",),
		legacy_source="OrderStateValidationService.java:54-63",
		contract_id="CHAR-ORDER-COMPLETE-01",
	),
	Gate(
		name="Material-availability gate (on hand minus reservations)",
		urs_ids=("URS-W1-008",),
		legacy_source="OrderStatesListenerServicePFTD.java:580",
		tc_id="TC-W1-009",
	),
	Gate(
		name="Transition legality (7-state machine)",
		urs_ids=("URS-W1-002",),
		legacy_source="OrderState.java:31-81 (canChangeTo)",
		tc_id="TC-W1-002",
	),
	Gate(
		name="Over-production hard stop",
		urs_ids=("URS-W1-010",),
		legacy_source="erpnext job_card.py:904-910 (anchor-adopt)",
		tc_id="TC-W1-011",
	),
	Gate(
		name="Stopped-order freeze",
		urs_ids=("URS-W1-011",),
		legacy_source="erpnext services/status.py:29-47 (anchor-adopt)",
		tc_id="TC-W1-012",
	),
	Gate(
		name="Closed order is terminal",
		urs_ids=("URS-W1-012",),
		legacy_source="erpnext work_order.py:1131-1132 (anchor-adopt)",
		tc_id="TC-W1-013",
	),
	Gate(
		name="Expiry policy on consumption and allocation",
		urs_ids=("URS-W1-013", "URS-W1-030"),
		legacy_source="ResourceManagementServiceImpl.java:1015-1027 (FEFO-advisory, no hard stop)",
		contract_id="CHAR-EXPIRY-ISSUE-01",
	),
	Gate(
		name="Recipe in-use lock",
		urs_ids=("URS-W1-017",),
		legacy_source="TechnologyValidationService.java:232-238 (checkIfTechnologyIsNotUsedInActiveOrder)",
		contract_id="CHAR-TECH-VALIDATE-01",
	),
)


def _registry_get() -> Callable[[str], object]:
	"""Contract lookup from the W0 harness, which is importable under either spelling.

	The harness is `tests/characterisation`; the CLI runs from the repository root and sees
	it as `tests.characterisation`, while the suites put `tests/` on the path and import it
	as a top-level `characterisation` package.
	"""
	for module_name in ("tests.characterisation.registry", "characterisation.registry"):
		try:
			return import_module(module_name).get
		except ImportError:
			continue
	raise RecordError("the W0 characterisation harness is not importable")


def sign_off_of(repo_root: Path, record: str) -> str | None:
	"""Sign-off recorded in a decision record, or `None` when it is absent/pending."""
	path = repo_root / record
	if not path.exists():
		return None
	match = SIGN_OFF.search(path.read_text(encoding="utf-8"))
	if not match:
		return None
	value = match.group("value").strip()
	return None if value.lower() in UNSIGNED else value


def _run_contract(contract) -> tuple[list[str], list[str]]:
	"""Execute every fixture case; returns (unexpected failures, proven divergences)."""
	failures: list[str] = []
	divergences: list[str] = []
	for case in contract.cases():
		expected_divergence = bool(contract.divergence and case.get("diverges"))
		try:
			contract.check(case)
		except AssertionError as error:
			(divergences if expected_divergence else failures).append(f"{case['id']}: {error}")
			continue
		if expected_divergence:
			failures.append(
				f"{case['id']}: declared divergence {contract.divergence.decision} no longer "
				"shows a delta — the target matches the legacy baseline again"
			)
	return failures, divergences


def contract_verdict(repo_root: Path, gate: Gate, contract) -> GateVerdict:
	"""Verdict of a contract-backed gate; raises `RecordError` on unrecorded drift."""
	failures, divergences = _run_contract(contract)
	if failures:
		raise RecordError(
			f"{gate.name}: contract {contract.id} failed without a recorded divergence — "
			+ "; ".join(failures)
		)
	resolution = contract.resolution()
	if not contract.divergence:
		return GateVerdict(
			gate=gate,
			verdict=VERDICT_PARITY,
			source=SOURCE_CONTRACT,
			detail=f"{contract.id} green against `{resolution.entrypoint}`",
		)
	if not divergences:
		raise RecordError(
			f"{gate.name}: {contract.id} declares divergence {contract.divergence.decision} but "
			"no fixture case is flagged `diverges`, so the delta is unproven"
		)
	sign_off = sign_off_of(repo_root, contract.divergence.record)
	if not sign_off:
		raise RecordError(
			f"{gate.name}: divergence {contract.divergence.decision} carries no business "
			f"sign-off in {contract.divergence.record} (name/role/date required)"
		)
	return GateVerdict(
		gate=gate,
		verdict=VERDICT_DIVERGENCE,
		source=SOURCE_CONTRACT,
		detail=f"{contract.id} shows the intended delta: {contract.divergence.summary}",
		sign_off=sign_off,
		decision=contract.divergence.decision,
	)


def anchor_verdict(gate: Gate, cited: dict[str, list[str]]) -> GateVerdict:
	"""Verdict of an adopted behaviour, proven by the test citing its mapped test case."""
	locations = cited.get(gate.tc_id or "", [])
	if not locations:
		raise RecordError(f"{gate.name}: no test cites {gate.tc_id}, so the adopted behaviour is unverified")
	return GateVerdict(
		gate=gate,
		verdict=VERDICT_PARITY,
		source=SOURCE_ANCHOR,
		detail=f"{gate.tc_id} verified by " + ", ".join(f"`{location}`" for location in sorted(locations)),
	)


def build_record(repo_root: Path, gates: tuple[Gate, ...] = W1_GATES) -> tuple[GateVerdict, ...]:
	"""Generate one verdict per gate; raises `RecordError` rather than claiming parity."""
	get = _registry_get()

	citations = collect_test_evidence(repo_root / "tests", repo_root)
	cited: dict[str, list[str]] = {}
	for citation in citations:
		for tc_id in citation.tc_ids:
			cited.setdefault(tc_id, []).append(citation.location)

	verdicts: list[GateVerdict] = []
	for gate in gates:
		if gate.contract_id:
			verdicts.append(contract_verdict(repo_root, gate, get(gate.contract_id)))
		else:
			verdicts.append(anchor_verdict(gate, cited))
	return tuple(verdicts)
