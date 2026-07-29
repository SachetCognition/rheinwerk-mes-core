"""Frappe app hooks for the consolidated Rheinwerk MES.

Anchor ERPNext DocTypes are never forked — every absorbed behaviour is registered
here as a doc_event, workflow, custom field or Property Setter owned by
`rheinwerk_mes`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

# doc_events = {}        # W1: execution gating hooks land here

# Fixtures exported with the app: Property Setters owned by `rheinwerk_mes` that
# extend anchor DocTypes without forking them (W0: `track_changes`, URS-W0-015).
fixtures = [
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

# The audit trail is a MES requirement, so it is (re)asserted on install and on
# every migration rather than configured once on a site.
after_install = "rheinwerk_mes.setup.audit.setup_audit_trail"
after_migrate = "rheinwerk_mes.setup.audit.setup_audit_trail"
