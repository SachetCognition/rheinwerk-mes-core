"""W3-3/W3-4 installer — group-ERP boundary site artefacts (URS-W3-010…014).

The boundary's own entities (`Boundary Message`, `ERP Sales Input`, `Group ERP Account Map`)
and the interface-health page are app-owned DocTypes/Pages and arrive with the app. The only
site artefacts created here are the ones that touch the substrate, and none of them forks an
anchor (programme rule 1):

| Anchor | Field | Purpose |
|---|---|---|
| `Work Order` | `rw_external_order_ref` | the group ERP's order reference, carried into the confirmation message (URS-W3-011 AC-1) |

Plus the read permissions the two health-surface audiences need (B. Vogel via
`Rheinwerk Business Viewer`, P. Krüger via `Rheinwerk Planner`) on the boundary queue.

Invoked from the `patches.txt` entry `rheinwerk_mes.setup.w3_boundary`; idempotent, so it is
safe to re-run on every `bench migrate`. Design: `docs/design/W3-erp-boundary.md`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.integration.boundary import contracts, outbound

INTEGRATION = "Integration"

PAGE_ROLES: tuple[str, ...] = (
	"Rheinwerk Planner",
	"Rheinwerk Business Viewer",
	"System Manager",
)


def custom_field_definitions() -> dict[str, list[dict]]:
	"""The single Custom Field the boundary needs on the anchor `Work Order`."""
	return {
		"Work Order": [
			{
				"fieldname": "rw_boundary_section",
				"label": _("Gruppen-ERP"),
				"fieldtype": "Section Break",
				"insert_after": "project",
				"collapsible": 1,
				"module": INTEGRATION,
			},
			{
				"fieldname": outbound.EXTERNAL_REF_FIELD,
				"label": _("Externe Auftragsreferenz"),
				"fieldtype": "Data",
				"insert_after": "rw_boundary_section",
				"in_standard_filter": 1,
				"description": _(
					"Referenz des Gruppen-ERP; wird mit der Fertigmeldung zurückgemeldet (URS-W3-011)."
				),
				"module": INTEGRATION,
			},
		]
	}


def setup_w3_boundary() -> None:
	"""Create every W3 boundary site artefact; idempotent."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	_grant_page_roles()
	frappe.clear_cache()


def _grant_page_roles() -> None:
	"""Make sure both health-surface audiences can open the interface-health page."""
	if not frappe.db.exists("Page", "interface-health"):
		return
	page = frappe.get_doc("Page", "interface-health")
	present = {row.role for row in page.roles}
	missing = [role for role in PAGE_ROLES if role not in present and frappe.db.exists("Role", role)]
	if not missing:
		return
	for role in missing:
		page.append("roles", {"role": role})
	page.flags.ignore_permissions = True
	page.save(ignore_permissions=True)


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w3_boundary()


def default_account_map() -> tuple[dict[str, str], ...]:
	"""The account map rows the fixture seeder installs (see `fixtures/seed.py`).

	Only the finished-goods warehouse is mapped on purpose: `RM Lager Nord` stays unmapped so
	that TC-W3-015's hold-queue path is exercised by the seeded site, not only by a fixture.
	"""
	return (
		{
			"warehouse_name": "FG Lager Süd",
			"stock_account_code": "1400-FERTIGWARE",
			"offset_account_code": "5900-BESTANDSVERAENDERUNG",
			"description": _("Fertigwarenlager Plant C — Gruppen-ERP-Konten laut Kontenrahmen."),
		},
	)


def account_map_doctype() -> str:
	return contracts.ACCOUNT_MAP_DOCTYPE
