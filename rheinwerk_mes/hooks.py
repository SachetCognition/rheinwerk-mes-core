"""Frappe app hooks — placeholder.

Wave W0 wires: app metadata, doc_events for gating listeners,
workflow fixtures for order/recipe state machines.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_license = "Proprietary"

after_install = "rheinwerk_mes.install.after_install"

# doc_events = {}        # W1: execution gating hooks land here
# fixtures = []          # W0: workflows, roles, custom fields
