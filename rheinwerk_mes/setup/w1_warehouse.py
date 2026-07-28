"""Wave W1 warehouse-fidelity setup — one idempotent entry point (W1-5 / W1-6).

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from `patches.txt`
(existing sites), so a clean install and a migration converge on the same schema. Every
artefact is created by committed code — never by hand on a site (programme rule 1):

* per-warehouse disposal strategy gains LEFO (URS-W1-020) and a `draft_makes_reservation`
  toggle (URS-W1-023) on the anchor Warehouse — Custom Fields, no fork;
* the anchor Stock Reservation Entry gains a `draft_reservation` flag and a Property
  Setter extending `voucher_type` so a draft outbound Stock Entry can own a reservation
  (URS-W1-023/024);
* Stock Entry rows and Batches can reference a Storage Location / Handling Unit
  (URS-W1-019/021), quantity still living only in the ledger;
* the substrate's per-item Serial and Batch toggle is switched on so batch-aware
  movements can post (URS-W1-021).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

WAREHOUSE_MODULE = "Warehouse"

#: SRE.voucher_type extended with "Stock Entry" so a draft outbound document can be the
#: reservation voucher (the anchor Literal ships without it).
SRE_VOUCHER_TYPE_OPTIONS = (
	"\nSales Order\nWork Order\nSubcontracting Inward Order\nProduction Plan"
	"\nSubcontracting Order\nStock Entry"
)


def custom_field_definitions() -> dict[str, list[dict]]:
	return {
		"Warehouse": [
			{
				"fieldname": "disposal_method",
				"label": _("Entnahmestrategie"),
				"fieldtype": "Select",
				"options": "\nFEFO\nFIFO\nLIFO\nLEFO",
				"insert_after": "warehouse_type",
				"in_standard_filter": 1,
				"module": WAREHOUSE_MODULE,
			},
			{
				"fieldname": "draft_makes_reservation",
				"label": _("Entwurf erzeugt Reservierung"),
				"fieldtype": "Check",
				"default": "0",
				"description": _(
					"Entwürfe ausgehender Bestandsbelege reservieren automatisch Bestand (Qcadoo-Semantik)."
				),
				"insert_after": "disposal_method",
				"module": WAREHOUSE_MODULE,
			},
		],
		"Stock Reservation Entry": [
			{
				"fieldname": "draft_reservation",
				"label": _("Entwurfsreservierung"),
				"fieldtype": "Check",
				"default": "0",
				"read_only": 1,
				"insert_after": "status",
				"module": WAREHOUSE_MODULE,
			},
		],
		"Stock Entry Detail": [
			{
				"fieldname": "storage_location",
				"label": _("Lagerplatz"),
				"fieldtype": "Link",
				"options": "Storage Location",
				"insert_after": "t_warehouse",
				"module": WAREHOUSE_MODULE,
			},
			{
				"fieldname": "handling_unit",
				"label": _("Ladeeinheit"),
				"fieldtype": "Link",
				"options": "Handling Unit",
				"insert_after": "storage_location",
				"module": WAREHOUSE_MODULE,
			},
		],
		"Batch": [
			{
				"fieldname": "storage_location",
				"label": _("Lagerplatz"),
				"fieldtype": "Link",
				"options": "Storage Location",
				"insert_after": "warehouse",
				"module": WAREHOUSE_MODULE,
			},
		],
	}


def setup_w1_warehouse() -> None:
	"""Create the W1 warehouse Custom Fields, Property Setter and stock toggle."""
	create_custom_fields(custom_field_definitions(), ignore_validate=True)
	make_property_setter(
		"Stock Reservation Entry",
		"voucher_type",
		"options",
		SRE_VOUCHER_TYPE_OPTIONS,
		"Text",
		validate_fields_for_doctype=False,
	)
	# Batch-aware movements need the substrate's per-item Serial/Batch toggle (URS-W1-021).
	frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
	frappe.clear_cache()
	frappe.db.commit()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_warehouse()
