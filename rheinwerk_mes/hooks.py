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
	# W1-2: post-transition side effects on the anchor Work Order. Reservations held by an
	# order are released when it reaches Declined or Abandoned (URS-W1-009); the effect is
	# keyed on the `state_history` row the state machine (URS-W1-001) appends.
	"Work Order": {
		"on_update": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
		"on_update_after_submit": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
	},
}
