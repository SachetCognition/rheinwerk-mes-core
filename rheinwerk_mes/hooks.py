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

after_install = [
	"rheinwerk_mes.install.after_install",
	# W1-4: recipe governance (URS-W1-014 … URS-W1-017).
	"rheinwerk_mes.setup.w1_recipe_gov.setup_w1_recipe_gov",
]

# Client-side additions to anchor forms; W1-4 renders the recipe's `gov_state` pill on the
# anchor BOM without forking it.
doctype_js = {
	"BOM": "recipe_isa88/bom_gov_state.js",
}

doc_events = {
	# W0-2: item-level UoM conversion invariants (URS-W0-004).
	# W1: execution-gating hooks are appended here.
	"Item": {
		"validate": "rheinwerk_mes.manufacturing_core.uom.validate_uom_conversions",
	},
	# W1-4: Accepted recipes are immutable and in-use recipes are locked
	# (URS-W1-016, URS-W1-017); changes need a new BOM version.
	"BOM": {
		"validate": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_update_after_submit": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_cancel": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
	},
}
