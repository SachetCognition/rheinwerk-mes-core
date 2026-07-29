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

RHEINWERK_MODULES = [
	"Manufacturing Core",
	"Execution Gating",
	"Genealogy",
	"Quality",
	"Warehouse",
	"Recipe ISA88",
	"Regulatory Hazmat",
	"Integration",
]

# Fixtures exported with the app: custom fields extending anchor DocTypes without
# forking them.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "in", RHEINWERK_MODULES]]},
]

after_install = "rheinwerk_mes.install.after_install"

doc_events = {
	# Every `exec_state` change funnels through one validator (URS-W1-001…004).
	"Work Order": {
		"before_insert": "rheinwerk_mes.manufacturing_core.exec_state.set_default_exec_state",
		"validate": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
		"before_update_after_submit": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
	},
}

# Ordered gate callbacks run before an `exec_state` change is written. Later waves append
# their gates here — no edit to the state machine needed. Each callable takes a
# `TransitionContext` and either appends German-first messages to `context.errors` /
# returns them, or throws its own modal.
rheinwerk_exec_state_gates = [
	"rheinwerk_mes.manufacturing_core.exec_state.reason_gate",
	# URS-W1-004: reconciliation with the anchor Work Order's posting-derived state.
	"rheinwerk_mes.manufacturing_core.exec_state.anchor_submit_gate",
	"rheinwerk_mes.manufacturing_core.exec_state.shortfall_gate",
]
