"""Frappe app hooks.

Layering (ARCHITECTURE.md): anchor ERPNext DocTypes are never forked — absorbed
behaviour is registered here as doc_events, workflows and custom fields owned by
`rheinwerk_mes` and installed from `rheinwerk_mes.setup`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

after_install = "rheinwerk_mes.install.after_install"

doc_events = {
	# W1-1: a newly created production order starts Pending (URS-W1-001).
	"Work Order": {
		"before_insert": "rheinwerk_mes.manufacturing_core.exec_state.set_default_exec_state",
	},
}

# Custom Fields extending the anchors travel with the app rather than being configured on
# a site by hand.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "in", ["Manufacturing Core"]]]},
]
