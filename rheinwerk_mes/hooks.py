"""Frappe app hooks for the consolidated Rheinwerk MES.

Anchor ERPNext DocTypes are never forked (ARCHITECTURE.md): the canonical Work Centre
extension (URS-W0-005, CDM-08, ADR-010) is registered here as `rheinwerk_mes` Custom
Fields on the `Workstation` anchor and exported with the app's fixtures, so the ERPNext
substrate stays byte-identical to upstream.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_email = "mes@rheinwerk-chemie.example"
app_license = "Proprietary"

required_apps = ["erpnext"]

# Fixtures exported with the app: the Custom Fields that extend the Workstation anchor
# without forking it.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "in", ["Manufacturing Core"]]],
	},
]

after_install = "rheinwerk_mes.install.after_install"
