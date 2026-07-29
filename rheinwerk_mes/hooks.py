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

# Ordered gate callbacks run before an `exec_state` change is written; each takes the
# state machine's `TransitionContext` and appends German-first refusal messages to it.
rheinwerk_exec_state_gates = [
	# URS-W1-005: acceptance needs planned dates, production line and a recipe reference.
	"rheinwerk_mes.execution_gating.acceptance_gate.acceptance_gate",
]
