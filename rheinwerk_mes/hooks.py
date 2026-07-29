"""Frappe app hooks.

Anchor ERPNext DocTypes are never forked: absorbed behaviour is registered here as a
doc_event, workflow or custom field owned by `rheinwerk_mes`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

# fixtures = []          # W0: workflows, roles, custom fields

doc_events = {
	"Work Order": {
		# URS-W1-007 — completion gate: recorded output > 0 and execution dates present.
		"validate": "rheinwerk_mes.execution_gating.gates.completion_gate",
	},
}
