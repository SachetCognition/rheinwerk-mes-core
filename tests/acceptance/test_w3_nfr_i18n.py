"""TC-W3-026 — German-first W3 screens and locale formats.

Verifies **URS-W3-022** (externalized strings with German first, dates DD.MM.YYYY, mass in kg,
no string concatenation) through **TC-W3-026** of `docs/test/TST-W3-planning-boundary.md`,
across the five W3 surfaces: the planning queue, the Linienplan board, the interface-health
page, the SCADA administration table and the dispatch station.

Same shape as TC-W2-049: a rendered-format assertion plus a repo scan of the W3 module
footprints for user-facing prose that bypasses the translation function. Reading the rendered
German screens with a native speaker stays a manual review recorded in the W3 evidence pack.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

frappe = pytest.importorskip("frappe")

#: The W3 module footprints — every package a W3 child (or the fan-in) owned.
W3_PACKAGES = (
	Path("rheinwerk_mes/manufacturing_core/planning"),
	Path("rheinwerk_mes/manufacturing_core/scheduling"),
	Path("rheinwerk_mes/integration/boundary"),
	Path("rheinwerk_mes/integration/scada"),
	Path("rheinwerk_mes/compliance"),
)
W3_SETUP = (
	Path("rheinwerk_mes/setup/w3_planning.py"),
	Path("rheinwerk_mes/setup/w3_scheduling.py"),
	Path("rheinwerk_mes/setup/w3_boundary.py"),
	Path("rheinwerk_mes/setup/w3_scada.py"),
	Path("rheinwerk_mes/setup/w3_hazmat.py"),
	Path("rheinwerk_mes/setup/w3_esignature.py"),
)
W3_ASSETS = (
	Path("rheinwerk_mes/public/js/esignature.js"),
	Path("rheinwerk_mes/manufacturing_core/page/schedule_board/schedule_board.js"),
	Path("rheinwerk_mes/integration/page/interface_health/interface_health.js"),
	Path("rheinwerk_mes/regulatory_hazmat/page/dispatch_label/dispatch_label.js"),
	Path("rheinwerk_mes/manufacturing_core/page/planning_queue/planning_queue.js"),
)

TRANSLATORS = frozenset({"_", "_lazy"})
UMLAUTS = "äöüßÄÖÜ"


def _is_user_facing(text: str) -> bool:
	if " " not in text:
		return False
	return any(char in text for char in UMLAUTS) or "{0}" in text or text.rstrip().endswith(".")


def _imports_frappe(source: str) -> bool:
	"""Whether a module can translate at all.

	The boundary contract validator, the external-sync register generator and the OPC-UA
	transport run *offline* — the contract fixture job validates them in CI without a site,
	so they cannot import `frappe._`. Their German text is contract/diagnostic text and a
	generated document, never a rendered screen, so the scan skips them rather than pushing
	them to import the platform for a translation nothing renders.
	"""
	return bool(re.search(r"^(?:import frappe|from frappe)", source, re.MULTILINE))


def _data_literals(tree: ast.Module) -> set[int]:
	"""Dict values that are *data*, not prose — a record name is not a translatable string.

	`{"warehouse_name": "FG Lager Süd"}` names a seeded record: translating it would look up
	a different warehouse. Only keys that read as message-bearing (label, description, …)
	stay in scope of the scan.
	"""
	message_keys = ("label", "description", "message", "title", "reason", "detail", "note", "text")
	exempt: set[int] = set()
	for node in ast.walk(tree):
		if not isinstance(node, ast.Dict):
			continue
		for key, value in zip(node.keys, node.values, strict=True):
			if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
				continue
			if any(marker in key.value for marker in message_keys):
				continue
			if isinstance(value, ast.Constant) and isinstance(value.value, str):
				exempt.add(id(value))
	return exempt


def _catalogue_literals(tree: ast.Module) -> set[int]:
	"""Literals held in a module-level catalogue (an UPPER_CASE constant).

	A catalogue is the German *message source*, not a rendered string: it is read through
	`_()` at render time, so wrapping it at definition time would translate it once at
	import against the wrong user's language — exactly what the requirement forbids.
	"""
	exempt: set[int] = set()
	for node in tree.body:
		if not isinstance(node, (ast.Assign, ast.AnnAssign)):
			continue
		targets = node.targets if isinstance(node, ast.Assign) else [node.target]
		names = [target.id for target in targets if isinstance(target, ast.Name)]
		if not names or not all(name.isupper() for name in names):
			continue
		if node.value is not None:
			exempt.update(
				id(child)
				for child in ast.walk(node.value)
				if isinstance(child, ast.Constant) and isinstance(child.value, str)
			)
	return exempt


def _untranslated_literals(source: str) -> list[str]:
	"""String constants that read as prose but never pass through `_()`/`_lazy()`."""
	tree = ast.parse(source)
	catalogued = _catalogue_literals(tree) | _data_literals(tree)
	translated = {
		id(argument)
		for node in ast.walk(tree)
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in TRANSLATORS
		for argument in node.args
	}
	docstrings = {
		id(node.body[0].value)
		for node in ast.walk(tree)
		if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
		and node.body
		and isinstance(node.body[0], ast.Expr)
		and isinstance(node.body[0].value, ast.Constant)
		and isinstance(node.body[0].value.value, str)
	}
	return [
		f"line {node.lineno}: {node.value!r}"
		for node in ast.walk(tree)
		if isinstance(node, ast.Constant)
		and isinstance(node.value, str)
		and id(node) not in translated
		and id(node) not in docstrings
		and id(node) not in catalogued
		and _is_user_facing(node.value)
	]


def test_every_user_facing_python_string_is_externalized(repo_root):
	"""URS-W3-022 AC-1 / TC-W3-026 step 2 — no hard-coded German outside `_()`."""
	offenders: list[str] = []
	files = [path for package in W3_PACKAGES for path in (repo_root / package).rglob("*.py")]
	files += [repo_root / path for path in W3_SETUP if (repo_root / path).exists()]
	for path in files:
		if "/doctype/" in path.as_posix() and path.name == "__init__.py":
			continue
		source = path.read_text(encoding="utf-8")
		if not _imports_frappe(source):
			continue
		for literal in _untranslated_literals(source):
			offenders.append(f"{path.relative_to(repo_root)} {literal}")
	assert not offenders, "user-facing strings must pass through frappe._(): " + "; ".join(offenders)


def test_every_user_facing_page_string_is_externalized(repo_root):
	"""URS-W3-022 AC-1 / TC-W3-026 step 2 — the W3 Desk assets translate through `__()`."""
	seen = 0
	for asset_path in W3_ASSETS:
		asset = repo_root / asset_path
		if not asset.exists():
			continue
		seen += 1
		source = asset.read_text(encoding="utf-8")
		rendered = re.findall(r">\s*([A-ZÄÖÜ][\wÄÖÜäöüß]+ [^<${]{3,})<", source)
		assert not rendered, f"untranslated literals in {asset_path.name}: {rendered}"
		assert "__(" in source, f"{asset_path.name} externalizes no string at all"
	assert seen, "no W3 client asset was found to check"


def test_schedule_board_renders_german_dates_and_kilograms(site):
	"""URS-W3-022 AC-2 / TC-W3-026 step 1 — the board formats server-side, DD.MM.YYYY and kg."""
	from test_w3_scheduling_support import draft_schedule

	board = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.board")
	schedule = draft_schedule(site)

	page = board.board_rows(schedule.name, start=0, page_length=5)

	assert page["rows"], "the board served no row for an existing schedule"
	for row in page["rows"]:
		assert re.match(r"\d{2}\.\d{2}\.\d{4}", row["planned_start"]), row["planned_start"]
		assert row["quantity"].endswith(" kg"), row["quantity"]
		assert "." not in row["quantity"], "German mass never carries a decimal point"


def test_state_labels_of_the_w3_surfaces_are_german():
	"""URS-W3-022 AC-1 — schedule, boundary and signature vocabularies all speak German."""
	schedule_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.scheduling.schedule_state")
	esignature = pytest.importorskip("rheinwerk_mes.compliance.esignature")

	assert schedule_state.state_labels()[schedule_state.APPROVED] == "Freigegeben"
	assert set(esignature.MEANINGS.values()) == {
		"Freigegeben",
		"Gesperrt",
		"Zertifiziert",
		"Rezeptur genehmigt",
	}
