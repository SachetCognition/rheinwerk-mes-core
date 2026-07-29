"""W0 German-first i18n baseline.

TC-W0-019 (URS-W0-016) — German rendering (DD.MM.YYYY, kg) and a scan that fails on
hard-coded user-facing strings anywhere in the app.
"""

from __future__ import annotations

import ast
from pathlib import Path

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


def test_tc_w0_019_german_date_rendering(site):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): the site renders dates as DD.MM.YYYY."""
	assert site.db.get_single_value("System Settings", "date_format") == "dd.mm.yyyy"
	formatdate = site.get_attr("frappe.utils.formatdate")
	assert formatdate("2026-02-02") == "02.02.2026"
	assert formatdate(site.db.get_value("Work Order", "PO-2026-0001", "planned_start_date")).count(".") == 2


def test_tc_w0_019_mass_is_expressed_in_kilograms(site):
	"""TC-W0-019 step 1 (URS-W0-016 AC-1): canonical mass quantities carry the kg stock
	UoM — on items, the BOM and the production order."""
	assert site.db.get_value("Item", "RW-CHM-0003", "stock_uom") == "Kg"
	assert site.db.get_value("BOM", "BOM-RW-CHM-0003-001", "uom") == "Kg"
	assert site.db.get_value("Work Order", "PO-2026-0001", "stock_uom") == "Kg"
	assert site.db.get_value("UOM", "Kg", "must_be_whole_number") == 0


def test_tc_w0_019_german_locale_defaults(site):
	"""TC-W0-019 (URS-W0-016 AC-1): the estate default locale is German/Europe-Berlin."""
	settings = site.get_single("System Settings")
	assert settings.country == "Germany"
	assert settings.time_zone == "Europe/Berlin"
