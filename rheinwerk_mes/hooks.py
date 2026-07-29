"""Frappe app hooks for the consolidated Rheinwerk MES.

Layering (ARCHITECTURE.md): anchor ERPNext DocTypes are never forked — every
absorbed behaviour is registered here as a doc_event, workflow or custom field
owned by `rheinwerk_mes`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

required_apps = ["erpnext"]

# Custom fields extending anchor DocTypes travel with the app.
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
]

after_install = "rheinwerk_mes.install.after_install"

doc_events = {
	"Work Order": {
		"before_insert": "rheinwerk_mes.manufacturing_core.exec_state.set_default_exec_state",
		"validate": "rheinwerk_mes.manufacturing_core.exec_state.record_exec_state_change",
		# `validate` does not run for update_after_submit, and rows appended in
		# `on_update_after_submit` land after `update_children()` — too late to persist.
		"before_update_after_submit": "rheinwerk_mes.manufacturing_core.exec_state.record_exec_state_change",
	},
}
