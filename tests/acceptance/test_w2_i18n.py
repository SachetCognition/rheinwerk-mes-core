"""TC-W2-049 — German-first W2 screens and locale formats.

Verifies **URS-W2-035** (externalized strings with German first, dates DD.MM.YYYY, mass in kg,
no string concatenation) through **TC-W2-049** of `docs/test/TST-W2-traceability-quality.md`,
across all four W2 surfaces: the Trace Ribbon, the inspection queue, the certificate and the
warehouse journeys.

Automated as a rendered-format assertion plus a repo scan of the W2 module footprints for
user-facing prose that bypasses the translation function — the same shape as TC-W1-037.
Reading the rendered German screens with a native speaker stays a manual review recorded in
the W2 evidence pack.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

frappe = pytest.importorskip("frappe")
coa = pytest.importorskip("rheinwerk_mes.quality.coa")
ribbon = pytest.importorskip("rheinwerk_mes.genealogy.ribbon")

#: The W2 module footprints — every package a W2 child owned.
W2_PACKAGES = (
	Path("rheinwerk_mes/genealogy"),
	Path("rheinwerk_mes/quality"),
	Path("rheinwerk_mes/recipe_isa88"),
	Path("rheinwerk_mes/regulatory_hazmat"),
)
W2_SETUP = (
	Path("rheinwerk_mes/setup/w2_genealogy.py"),
	Path("rheinwerk_mes/setup/w2_quality.py"),
	Path("rheinwerk_mes/setup/w2_isa88.py"),
	Path("rheinwerk_mes/setup/w2_warehouse.py"),
	Path("rheinwerk_mes/setup/w2_rbac.py"),
)
W2_PAGES = (
	Path("rheinwerk_mes/genealogy/page/trace_ribbon/trace_ribbon.js"),
	Path("rheinwerk_mes/quality/page/inspection_queue/inspection_queue.js"),
)

TRANSLATORS = frozenset({"_", "_lazy"})
UMLAUTS = "äöüßÄÖÜ"

BATCH = "BATCH-A-0001"


def _is_user_facing(text: str) -> bool:
	if " " not in text:
		return False
	return any(char in text for char in UMLAUTS) or "{0}" in text or text.rstrip().endswith(".")


def _catalogue_literals(tree: ast.Module) -> set[int]:
	"""Literals held in a module-level catalogue (an UPPER_CASE constant).

	A catalogue is the German *message source*, not a rendered string: it is read through
	`_()` at render time (`_(VALIDATOR_LABELS[...])`) or handed to the platform, which
	translates it itself (workflow action labels). Wrapping the literal at definition time
	would translate it once at import against the wrong user's language, which is exactly
	what the requirement forbids — so the catalogue entries are exempted here and their
	*consumption* is asserted separately by `test_message_catalogues_are_read_through_the_translator`.
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
	catalogued = _catalogue_literals(tree)
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


#: Catalogue → the module that must read it through the translator (URS-W2-035 AC-1).
RENDERED_CATALOGUES = (
	(Path("rheinwerk_mes/quality/queue.py"), "EMPTY_STATE_TITLE"),
	(Path("rheinwerk_mes/recipe_isa88/governance.py"), "VALIDATOR_LABELS"),
	(Path("rheinwerk_mes/genealogy/qa_state.py"), "STATE_LABELS"),
)


def test_expiry_renders_german_on_the_ribbon(site):
	"""URS-W2-035 AC-1 / TC-W2-049 step 2 — BATCH-A-0001's expiry reads 31.12.2026."""
	if not site.db.exists("Batch", BATCH):
		pytest.skip(f"programme fixture Batch {BATCH} not seeded on this site")
	model = ribbon.ribbon(BATCH)
	assert model["focus"]["expiry_date"] == "31.12.2026"


def test_quantities_render_as_tabular_kilograms():
	"""URS-W2-035 AC-2 / TC-W2-049 step 3 — 480 kg reads as German mass with its unit."""
	assert coa.kg(480) == "480 kg"
	assert coa.kg(480.5) == "480,5 kg"


def test_status_labels_are_german(site):
	"""URS-W2-035 AC-1 — the pills the ribbon and the CoA share speak German."""
	qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")
	assert qa_state.STATE_LABELS[qa_state.BLOCKED] == "Gesperrt"
	assert set(coa.STATUS_LABELS.values()) == {"Ausgestellt", "Ersetzt"}


def test_every_user_facing_python_string_is_externalized(repo_root):
	"""URS-W2-035 AC-1 / TC-W2-049 step 1 — no hard-coded German outside `_()`."""
	offenders: list[str] = []
	files = [path for package in W2_PACKAGES for path in (repo_root / package).rglob("*.py")]
	files += [repo_root / path for path in W2_SETUP if (repo_root / path).exists()]
	for path in files:
		if "/doctype/" in path.as_posix() and path.name == "__init__.py":
			continue
		for literal in _untranslated_literals(path.read_text(encoding="utf-8")):
			offenders.append(f"{path.relative_to(repo_root)} {literal}")
	assert not offenders, "user-facing strings must pass through frappe._(): " + "; ".join(offenders)


def test_message_catalogues_are_read_through_the_translator(repo_root):
	"""URS-W2-035 AC-1 — a German catalogue is translated where it is rendered, not where it is declared."""
	for path, name in RENDERED_CATALOGUES:
		asset = repo_root / path
		if not asset.exists():
			continue
		source = asset.read_text(encoding="utf-8")
		assert re.search(rf"_\(\s*{name}\b", source), f"{path.name} must render {name} through _()"


def test_every_user_facing_page_string_is_externalized(repo_root):
	"""URS-W2-035 AC-1 / TC-W2-049 step 1 — the W2 Desk pages translate through `__()`."""
	for page in W2_PAGES:
		asset = repo_root / page
		if not asset.exists():
			continue
		source = asset.read_text(encoding="utf-8")
		rendered = re.findall(r">\s*([A-ZÄÖÜ][\wÄÖÜäöüß]+ [^<${]{3,})<", source)
		assert not rendered, f"untranslated literals in {page.name}: {rendered}"
		assert "__(" in source, f"{page.name} externalizes no string at all"


def test_certificate_template_renders_dates_and_masses_through_the_helpers(repo_root):
	"""URS-W2-035 AC-1/AC-2 — the printed certificate uses the same locale helpers."""
	template = repo_root / "rheinwerk_mes/quality/templates/coa_certificate.html"
	if not template.exists():
		pytest.skip("CoA template not present in this checkout")
	source = template.read_text(encoding="utf-8")
	assert "{{ _(" in source, "the certificate body must translate its labels"
	assert re.search(r"\d{4}-\d{2}-\d{2}", source) is None, "no ISO date may reach the certificate"
