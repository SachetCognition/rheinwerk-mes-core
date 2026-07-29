"""Frappe app hooks — placeholder.

Wave W0 wires: app metadata, doc_events for gating listeners,
workflow fixtures for order/recipe state machines.
"""
app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

# fixtures = []          # W0: workflows, roles, custom fields

doc_events = {
	# W1-1: only legal `exec_state` transitions are permitted (URS-W1-002).
	"Work Order": {
		"validate": "rheinwerk_mes.execution_gating.order_state_gating.enforce_legal_transition",
	},
}
