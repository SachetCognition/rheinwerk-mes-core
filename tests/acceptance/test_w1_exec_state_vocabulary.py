"""TC-W1-005 — the vocabulary rule: no unqualified "status" (offline).

Verifies **URS-W1-004 AC-3** through **TC-W1-005** of
`docs/test/TST-W1-production-core.md` against the committed field/label catalogue;
the site-backed half of TC-W1-005 lives in `test_w1_exec_state_reconciliation.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: The unqualified word only — `exec_state`, `qa_state`, `gov_state` and German
#: compounds such as "Statusverlauf" are the sanctioned vocabulary (ADR-004).
UNQUALIFIED_STATUS = re.compile(r"(?<![\w-])status(?![\w-])", re.IGNORECASE)


def test_no_unqualified_status_in_committed_field_definitions(repo_root: Path):
	"""URS-W1-004 AC-3 / TC-W1-005 — repo-side field/label catalogue is clean."""
	offenders: list[str] = []
	app = repo_root / "rheinwerk_mes"

	for path in app.rglob("*.json"):
		payload = json.loads(path.read_text(encoding="utf-8"))
		if payload.get("doctype") != "DocType":
			continue
		for field in payload.get("fields", []):
			for key in ("fieldname", "label"):
				value = field.get(key) or ""
				if UNQUALIFIED_STATUS.search(value):
					offenders.append(f"{path.name}:{field.get('fieldname')}:{key}={value}")

	for path in (app / "setup").rglob("*.py"):
		source = path.read_text(encoding="utf-8")
		for match in re.finditer(r'"(fieldname|label)":\s*_?\(?"([^"]*)"', source):
			if UNQUALIFIED_STATUS.search(match.group(2)):
				offenders.append(f"{path.name}:{match.group(1)}={match.group(2)}")

	assert not offenders, f"unqualified 'status' in canonical definitions: {offenders}"
