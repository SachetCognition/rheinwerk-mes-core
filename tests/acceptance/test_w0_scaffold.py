"""W0-1 scaffold acceptance — TC-W0-001, TC-W0-002 (URS-W0-001).

TC-W0-001: the app installs and registers all eight W0 module skeletons; later waves may add
modules of their own (W3 adds `Compliance` for the DEC-W2-029 signatures), which must be
registered the same way — hence the split between the W0 floor and the shipped set.
TC-W0-002: no anchor DocType is forked — `rheinwerk_mes` ships no copy of an
anchor DocType schema; extensions may only exist as Custom Field / Property
Setter / linked DocType records.
"""

from __future__ import annotations

ANCHOR_DOCTYPES = ("Item", "Workstation", "BOM", "Work Order", "Warehouse", "UOM")

#: The eight modules W0 defines — the floor every later wave keeps.
W0_MODULES = (
	"Manufacturing Core",
	"Execution Gating",
	"Genealogy",
	"Quality",
	"Warehouse",
	"Recipe ISA88",
	"Regulatory Hazmat",
	"Integration",
)

#: Modules added by later waves, each with the wave that introduced it.
LATER_MODULES = ("Compliance",)

MODULES = W0_MODULES + LATER_MODULES


def test_modules_txt_lists_every_module_of_the_app(repo_root):
	listed = [
		line.strip()
		for line in (repo_root / "rheinwerk_mes" / "modules.txt").read_text().splitlines()
		if line.strip()
	]
	assert set(W0_MODULES) <= set(listed)
	assert set(listed) == set(MODULES)
	assert len(listed) == len(MODULES)


def test_module_packages_exist(repo_root):
	for module in MODULES:
		package = repo_root / "rheinwerk_mes" / module.lower().replace(" ", "_")
		assert (package / "__init__.py").exists(), f"missing module package for {module}"


def test_app_ships_no_anchor_doctype_schema(repo_root):
	"""No anchor DocType JSON may live inside this app (anchors are never forked)."""
	shipped = {p.stem for p in (repo_root / "rheinwerk_mes").rglob("*.json") if p.parent.name == p.stem}
	forked = {name.lower().replace(" ", "_") for name in ANCHOR_DOCTYPES} & shipped
	assert not forked, f"anchor DocType schema forked into rheinwerk_mes: {sorted(forked)}"


def test_modules_registered_on_site(site):
	registered = set(site.get_all("Module Def", filters={"app_name": "rheinwerk_mes"}, pluck="name"))
	assert set(MODULES) <= registered


def test_anchor_doctypes_owned_by_substrate(site):
	for doctype in ANCHOR_DOCTYPES:
		owner_app = site.db.get_value("DocType", doctype, "module")
		assert owner_app, f"anchor DocType {doctype} missing on the substrate"
		app = site.db.get_value("Module Def", owner_app, "app_name")
		assert app in ("frappe", "erpnext"), f"anchor DocType {doctype} was re-homed to {app}"
