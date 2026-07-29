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

# The app is installed alongside ERPNext on one site; the substrate is a
# hard dependency (anchor DocTypes: Item, Workstation, BOM, Work Order,
# Warehouse, UOM) — never forked, only extended.
required_apps = ["erpnext"]

# The eight target modules (CONSOLIDATION.md); mirrors modules.txt.
MODULES = [
	"Manufacturing Core",
	"Execution Gating",
	"Genealogy",
	"Quality",
	"Warehouse",
	"Recipe ISA88",
	"Regulatory Hazmat",
	"Integration",
]

# Extensions to anchor DocTypes ship as fixtures owned by this app's modules,
# so nothing is written into the ERPNext schema itself.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "in", MODULES]]},
	{"dt": "Property Setter", "filters": [["module", "in", MODULES]]},
]

after_install = "rheinwerk_mes.install.after_install"

# doc_events = {}  # W1: execution-gating hooks land here
