"""Frappe app hooks for the consolidated Rheinwerk MES.

Layering (ARCHITECTURE.md): anchor ERPNext DocTypes are never forked — every
absorbed behaviour is registered here as a doc_event, workflow or custom field
owned by `rheinwerk_mes`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_email = "mes@rheinwerk-chemie.example"
app_license = "Proprietary"

required_apps = ["erpnext"]

# Fixtures exported with the app: custom fields, property setters, workflows and
# roles that extend anchor DocTypes without forking them.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
]

after_install = "rheinwerk_mes.install.after_install"

doc_events = {
	# W0-2: item-level UoM conversion invariants (URS-W0-004).
	# W1: execution-gating hooks are appended here.
	"Item": {
		"validate": "rheinwerk_mes.manufacturing_core.uom.validate_uom_conversions",
	},
	# W1-6: draft outbound Stock Entries make/release reservations (URS-W1-023/024).
	"Stock Entry": {
		"on_update": "rheinwerk_mes.warehouse.reservations.on_stock_entry_update",
		"on_submit": "rheinwerk_mes.warehouse.reservations.on_stock_entry_submit",
		"on_cancel": "rheinwerk_mes.warehouse.reservations.on_stock_entry_cancel",
		"on_trash": "rheinwerk_mes.warehouse.reservations.on_stock_entry_trash",
	},
}
