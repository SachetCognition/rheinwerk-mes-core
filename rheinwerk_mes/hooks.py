"""Frappe app hooks — placeholder.

Wave W0 wires: app metadata, doc_events for gating listeners,
workflow fixtures for order/recipe state machines.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

# doc_events = {}        # W1: execution gating hooks land here
# fixtures = []          # W0: workflows, roles, custom fields

# W1: ordered gate callbacks run by the production-order state machine (URS-W1-001) before a
# state change is written; later requirements append their gates here, so the state machine
# itself is never edited. Each callable takes a `TransitionContext` and refuses through it
# (see `rheinwerk_mes.execution_gating.gates`).
rheinwerk_exec_state_gates = [
	# URS-W1-008: components must be available (on hand minus reservations) at order start.
	"rheinwerk_mes.execution_gating.gates.material_availability_gate",
]
