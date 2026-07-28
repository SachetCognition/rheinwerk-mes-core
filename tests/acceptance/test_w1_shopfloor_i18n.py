"""TC-W1-037 — German-first W1 screens.

Verifies **URS-W1-034** (externalized strings, DD.MM.YYYY dates, kg quantities on every W1
screen, gate-refusal texts included) through **TC-W1-037** of
`docs/test/TST-W1-production-core.md`.

Automated as a rendered-format assertion plus a repo scan of the W1-7 footprint for
user-facing strings that bypass the translation function. Reading the rendered German
screens with a native speaker stays a manual review recorded in the W1 evidence pack.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

frappe = pytest.importorskip("frappe")
formatting = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.formatting")

SHOPFLOOR_PY = Path("rheinwerk_mes/manufacturing_core/shopfloor")
SETUP_PY = (
	Path("rheinwerk_mes/setup/w1_shopfloor.py"),
	Path("rheinwerk_mes/setup/w1_roles.py"),
)
PAGE_JS = Path("rheinwerk_mes/manufacturing_core/page/shop_floor_terminal/shop_floor_terminal.js")

#: Functions that externalize a string: the translator and the lazy message-id marker.
TRANSLATORS = frozenset({"_", "_lazy"})

#: A literal is user-facing when it reads as a sentence: umlauts, a placeholder or a
#: closing period in a multi-word string. Identifiers ("Work Order") never match.
UMLAUTS = "äöüßÄÖÜ"


def _is_user_facing(text: str) -> bool:
	if " " not in text:
		return False
	return any(char in text for char in UMLAUTS) or "{0}" in text or text.rstrip().endswith(".")


def _untranslated_literals(source: str) -> list[str]:
	"""String constants that read as prose but never pass through `_()`/`_lazy()`."""
	import ast

	tree = ast.parse(source)
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
		and _is_user_facing(node.value)
	]


def test_dates_and_masses_render_german_first():
	"""URS-W1-034 AC-1 / TC-W1-037 step 1 — DD.MM.YYYY and kg from the shared helpers."""
	assert formatting.format_date_de("2026-06-30") == "30.06.2026"
	assert formatting.format_datetime_de("2026-06-30 14:05:00") == "30.06.2026 14:05"
	assert formatting.format_kg(500) == "500,000 kg"


def test_every_user_facing_python_string_is_externalized(repo_root):
	"""URS-W1-034 AC-2 / TC-W1-037 step 2 — no hard-coded German outside `_()`."""
	offenders = []
	files = list((repo_root / SHOPFLOOR_PY).glob("*.py")) + [repo_root / path for path in SETUP_PY]
	for path in files:
		for literal in _untranslated_literals(path.read_text(encoding="utf-8")):
			offenders.append(f"{path.name} {literal}")
	assert not offenders, "user-facing strings must pass through frappe._(): " + "; ".join(offenders)


def test_every_user_facing_page_string_is_externalized(repo_root):
	"""URS-W1-034 AC-2 / TC-W1-037 step 2 — the terminal page translates through `__()`."""
	source = (repo_root / PAGE_JS).read_text(encoding="utf-8")
	rendered = re.findall(r">\s*([A-ZÄÖÜ][\wÄÖÜäöüß]+ [^<${]{3,})<", source)
	assert not rendered, f"untranslated literals in the terminal page: {rendered}"
	assert "__(" in source


def test_refusal_texts_are_german_and_name_the_record(site):
	"""URS-W1-034 / TC-W1-037 — a gate refusal speaks German and names rule and record."""
	job_execution = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.job_execution")
	with pytest.raises(frappe.ValidationError) as refusal:
		job_execution.job_queue("PO-NICHT-VORHANDEN")
	message = str(refusal.value)
	assert "PO-NICHT-VORHANDEN" in message
	assert "Fertigungsauftrag" in message
