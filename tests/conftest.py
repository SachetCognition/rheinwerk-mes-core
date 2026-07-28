"""Shared pytest wiring for the Rheinwerk MES suites.

Two kinds of test run from this tree:

* **offline** — pure-python parity contracts and repo-structure checks; no site needed.
* **site-backed** — integration/acceptance tests that need a Frappe site with the
  ERPNext substrate and `rheinwerk_mes` installed. They request the `site` fixture,
  which connects to `$FRAPPE_SITE` (default `dev.localhost`) in `$BENCH_PATH`
  (default `~/frappe-bench`) and rolls the transaction back afterwards.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def bench_path() -> Path:
	return Path(os.environ.get("BENCH_PATH", Path.home() / "frappe-bench")).resolve()


def site_name() -> str:
	return os.environ.get("FRAPPE_SITE", "dev.localhost")


@pytest.fixture(scope="session")
def repo_root() -> Path:
	return REPO_ROOT


@pytest.fixture(scope="session")
def _frappe_session():
	sites_path = bench_path() / "sites"
	if not (sites_path / site_name()).exists():
		pytest.skip(f"Frappe site {site_name()} not available under {sites_path}")

	os.chdir(sites_path)
	frappe = pytest.importorskip("frappe")
	frappe.init(site=site_name(), sites_path=str(sites_path))
	frappe.connect()
	frappe.flags.in_test = True
	frappe.set_user("Administrator")
	yield frappe
	frappe.destroy()


@pytest.fixture
def site(_frappe_session):
	"""Per-test Frappe connection; every test's writes are rolled back."""
	frappe = _frappe_session
	frappe.set_user("Administrator")
	yield frappe
	frappe.db.rollback()
