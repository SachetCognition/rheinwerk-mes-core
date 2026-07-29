"""W0 German-first i18n baseline.

TC-W0-019 (URS-W0-016) — German rendering (DD.MM.YYYY, kg), the design-conformance
baseline for W0 list views (mono identifiers, icon + label + colour status pills) and
a scan that fails on hard-coded user-facing strings anywhere in the app.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest

LOCALE_MODULE = "rheinwerk_mes.setup.locale"


@pytest.fixture(scope="module")
def app_hooks(repo_root):
	"""`hooks.py` loaded straight from the working tree, so the asset registrations can be
	asserted without a Frappe environment."""
	spec = importlib.util.spec_from_file_location("rheinwerk_mes_hooks", repo_root / "rheinwerk_mes/hooks.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


@pytest.fixture
def site_locale(site):
	return site.get_attr(LOCALE_MODULE)


TRANSLATABLE_KEYWORDS = frozenset({"title", "label", "description"})
LOCALISED_CALLS = frozenset({"throw", "msgprint"})
TRANSLATABLE_KEYS = frozenset({"label", "description", "title"})


def _is_translation_call(node: ast.expr) -> bool:
	return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"


def _is_literal_text(node: ast.expr) -> bool:
	"""A string the user could read that was never passed through `frappe._()`."""
	if isinstance(node, ast.Constant):
		return isinstance(node.value, str) and node.value.strip() != ""
	return isinstance(node, ast.JoinedStr)


class _HardCodedStringScan(ast.NodeVisitor):
	"""Flags user-facing text that bypasses translation, and translated text that is
	built by concatenation instead of `.format()` (URS-W0-016)."""

	def __init__(self, path: Path) -> None:
		self.path = path
		self.violations: list[str] = []

	def _record(self, node: ast.AST, reason: str) -> None:
		self.violations.append(f"{self.path}:{node.lineno}: {reason}")

	def visit_Call(self, node: ast.Call) -> None:
		if _is_translation_call(node):
			for argument in node.args:
				if isinstance(argument, ast.JoinedStr | ast.BinOp):
					self._record(node, "translated text is interpolated — use _('…{0}').format(…)")
		elif isinstance(node.func, ast.Attribute) and node.func.attr in LOCALISED_CALLS:
			first = node.args[0] if node.args else None
			if first is not None and _is_literal_text(first):
				self._record(node, f"{node.func.attr}() message is not wrapped in _()")
		for keyword in node.keywords:
			if keyword.arg in TRANSLATABLE_KEYWORDS and _is_literal_text(keyword.value):
				self._record(node, f"{keyword.arg}= is not wrapped in _()")
		self.generic_visit(node)

	def visit_Dict(self, node: ast.Dict) -> None:
		for key, value in zip(node.keys, node.values, strict=True):
			if isinstance(key, ast.Constant) and key.value in TRANSLATABLE_KEYS:
				if _is_literal_text(value):
					self._record(node, f"dict entry {key.value!r} is not wrapped in _()")
		self.generic_visit(node)


def test_tc_w0_019_no_hard_coded_user_facing_strings(repo_root):
	"""TC-W0-019 step 2 (URS-W0-016 AC-2): every user-facing string in `rheinwerk_mes`
	goes through `frappe._()` and none is assembled by concatenation."""
	violations: list[str] = []
	for path in sorted((repo_root / "rheinwerk_mes").rglob("*.py")):
		scan = _HardCodedStringScan(path.relative_to(repo_root))
		scan.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
		violations.extend(scan.violations)
	assert not violations, "hard-coded user-facing strings:\n" + "\n".join(violations)


# Object keys whose value is read by a person, and the desk translation call.
JS_TRANSLATION_CALL = re.compile(r"__\(")
JS_LITERAL_KEY_VALUE = re.compile(r"\b(label|title|description)\s*:\s*([\"'`])")
JS_MESSAGE_CALL = re.compile(r"frappe\.(?:throw|msgprint|show_alert)\(\s*([\"'`])")
JS_INTERPOLATED_TRANSLATION = re.compile(r"__\(\s*(?:`[^`]*\$\{|[\"'][^\"']*[\"']\s*\+)")


def _javascript_violations(source: str, path: Path) -> list[str]:
	"""User-facing text in desk scripts that bypasses `__()`, or is interpolated into it."""
	violations = []
	for number, line in enumerate(source.splitlines(), start=1):
		code = line.split("//", 1)[0]
		for pattern, reason in (
			(JS_LITERAL_KEY_VALUE, "literal is not wrapped in __()"),
			(JS_MESSAGE_CALL, "message is not wrapped in __()"),
		):
			if pattern.search(code) and not JS_TRANSLATION_CALL.search(code):
				violations.append(f"{path}:{number}: {reason}")
		if JS_INTERPOLATED_TRANSLATION.search(code):
			violations.append(f"{path}:{number}: translated text is interpolated — use __() with arguments")
	return violations


def test_tc_w0_019_no_hard_coded_strings_in_desk_scripts(repo_root):
	"""TC-W0-019 step 2 (URS-W0-016 AC-2): the front-end obeys the same discipline —
	every label a user reads goes through `__()`."""
	scripts = sorted((repo_root / "rheinwerk_mes").rglob("*.js"))
	if not scripts:
		pytest.skip("no desk scripts yet — W0 conforms through CSS only")
	violations: list[str] = []
	for path in scripts:
		violations.extend(
			_javascript_violations(path.read_text(encoding="utf-8"), path.relative_to(repo_root))
		)
	assert not violations, "hard-coded user-facing strings:\n" + "\n".join(violations)


def test_tc_w0_019_german_date_rendering(site):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): the site renders dates as DD.MM.YYYY."""
	assert site.db.get_single_value("System Settings", "date_format") == "dd.mm.yyyy"
	formatdate = site.get_attr("frappe.utils.formatdate")
	assert formatdate("2026-02-02") == "02.02.2026"
	assert formatdate(site.db.get_value("Work Order", "PO-2026-0001", "planned_start_date")).count(".") == 2


def test_tc_w0_019_batch_expiry_renders_as_german_date(site):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): BATCH-A-0001's expiry reads 31.12.2026 wherever
	a W0 screen renders it — the value is formatted by the site's date format, so this is
	the same string the list view, the form and the print format emit."""
	expiry = site.db.get_value("Batch", "BATCH-A-0001", "expiry_date")
	assert site.format(expiry, {"fieldtype": "Date"}) == "31.12.2026"
	assert site.format_value(expiry, {"fieldtype": "Date"}) == "31.12.2026"
	# …and the shelf life is on the list view, not just the form.
	assert site.get_meta("Batch").get_field("expiry_date").in_list_view == 1


def test_tc_w0_019_mass_is_expressed_in_kilograms(site):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): canonical mass quantities carry the kg stock
	UoM — on items, the BOM and the production order."""
	assert site.db.get_value("Item", "RW-CHM-0003", "stock_uom") == "Kg"
	assert site.db.get_value("BOM", "BOM-RW-CHM-0003-001", "uom") == "Kg"
	assert site.db.get_value("Work Order", "PO-2026-0001", "stock_uom") == "Kg"
	assert site.db.get_value("UOM", "Kg", "must_be_whole_number") == 0


def test_tc_w0_019_batch_mass_is_expressed_in_kilograms(site, site_locale):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): batch quantities are read in kg, inherited from
	the item's stock UoM, and kg is the estate default for new stock items."""
	assert site.db.get_value("Batch", "BATCH-A-0001", "stock_uom") == site_locale.MASS_UOM
	assert site.db.get_single_value("Stock Settings", "stock_uom") == site_locale.MASS_UOM


def test_tc_w0_019_german_locale_defaults(site, site_locale):
	"""TC-W0-019 (URS-W0-016 AC-1): the estate default locale is German — language, country,
	time zone, date format and German number separators."""
	settings = site.get_single("System Settings")
	assert settings.language == site_locale.LANGUAGE
	assert settings.country == site_locale.COUNTRY
	assert settings.time_zone == site_locale.TIME_ZONE
	assert settings.date_format == site_locale.DATE_FORMAT
	assert settings.number_format == site_locale.NUMBER_FORMAT
	assert settings.first_day_of_the_week == site_locale.FIRST_DAY_OF_WEEK
	assert site.format(1234.5, {"fieldtype": "Float"}) == "1.234,50"


def test_tc_w0_019_locale_is_reapplied_by_setup(site, site_locale):
	"""TC-W0-019 (URS-W0-016 AC-1): the locale is committed configuration, so a site that
	drifted converges again on `bench migrate` — not by hand."""
	site.db.set_single_value("System Settings", "date_format", "yyyy-mm-dd")
	site_locale.install_locale()
	assert site.db.get_single_value("System Settings", "date_format") == site_locale.DATE_FORMAT


@pytest.fixture(scope="module")
def stylesheet(repo_root, app_hooks):
	"""The design baseline, registered app-wide rather than per screen."""
	source = repo_root / "rheinwerk_mes/public/css/rheinwerk_mes.css"
	assert app_hooks.app_include_css == "/assets/rheinwerk_mes/css/rheinwerk_mes.css"
	return source.read_text(encoding="utf-8")


def test_tc_w0_019_identifiers_render_in_mono(stylesheet):
	"""TC-W0-019 step 3: identifiers (item codes, batch numbers, order numbers) render in
	mono — in list columns and on the form — addressed by field name, so the anchor list
	views conform without being forked."""
	assert "IBM Plex Mono" in stylesheet
	assert "tabular-nums" in stylesheet
	for fieldname in ("name", "item_code", "batch_id", "bom_no", "production_item", "work_order"):
		assert f'[data-fieldname="{fieldname}"]' in stylesheet, fieldname
	assert ".list-row-col" in stylesheet


def test_tc_w0_019_status_pills_are_never_colour_only(stylesheet):
	"""TC-W0-019 step 3: a status pill carries icon + label + colour. The desk badge ships
	colour + label; the icon is added per semantic theme, one glyph per colour."""
	assert ".es-badge::before" in stylesheet
	assert ".indicator-pill:not(.no-indicator-dot)::before" in stylesheet
	for theme in ("blue", "green", "amber", "red", "violet"):
		assert f'[data-theme="{theme}"]' in stylesheet, theme
	# One distinct glyph per theme, so colour is never the only signal.
	glyphs = re.findall(r'content: "(.)"', stylesheet)
	assert len(glyphs) == len(set(glyphs)) >= 5, glyphs
