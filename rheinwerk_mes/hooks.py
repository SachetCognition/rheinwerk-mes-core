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

required_apps = ["erpnext"]

# Fixtures exported with the app: custom fields, property setters, workflows and
# roles that extend anchor DocTypes without forking them.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
]

after_install = [
	"rheinwerk_mes.install.after_install",
	# W1-4: recipe governance (URS-W1-014 … URS-W1-017).
	"rheinwerk_mes.setup.w1_recipe_gov.setup_w1_recipe_gov",
	# W1-2/W1-3: execution gating + anchor hard-stop configuration (URS-W1-005 … URS-W1-013).
	"rheinwerk_mes.setup.w1_gating.setup_w1_gating",
	# W2-1/2/3: canonical Batch, `qa_state` workflow, genealogy tables (URS-W2-005/006).
	"rheinwerk_mes.setup.w2_genealogy.setup_w2_genealogy",
	# W1-8: role gating runs last so it can also stamp the governance workflow's
	# transitions (URS-W1-029).
	"rheinwerk_mes.setup.w1_roles.setup_w1_roles",
]

# Client-side additions to anchor forms; W1-4 renders the recipe's `gov_state` pill on the
# anchor BOM without forking it.
doctype_js = {
	"BOM": "recipe_isa88/bom_gov_state.js",
}

# W1-7: Desk/Terminal density tokens and status pills for the shop-floor screens.
# W2-1: the Trace Ribbon shares the shop-floor tokens and adds its own ribbon layout.
app_include_css = [
	"/assets/rheinwerk_mes/css/shopfloor.css",
	"/assets/rheinwerk_mes/css/trace_ribbon.css",
]

doc_events = {
	# W0-2: item-level UoM conversion invariants (URS-W0-004).
	# W1: execution-gating hooks are appended here.
	"Item": {
		"validate": "rheinwerk_mes.manufacturing_core.uom.validate_uom_conversions",
	},
	# W1-6: draft outbound Stock Entries make/release reservations (URS-W1-023/024).
	# W1-3: consuming a batch past its expiry is refused (URS-W1-013, policy URS-W1-030) —
	# the substrate skips its own expiry throw for Stock Entry vouchers.
	"Stock Entry": {
		"validate": [
			# Auto-allocation runs first so the expiry hard stop also sees the batches the
			# policy itself chose (URS-W1-030).
			"rheinwerk_mes.execution_gating.allocation.allocate_stock_entry_batches",
			"rheinwerk_mes.execution_gating.expiry.enforce_batch_expiry",
			# W2-3: a Blocked batch may not be consumed, and stock may not leave a
			# quarantine location without the QA/clerk role (URS-W2-011, URS-W2-012).
			"rheinwerk_mes.genealogy.blocking.enforce_blocked_batch_consumption",
			"rheinwerk_mes.genealogy.quarantine.enforce_quarantine_exit",
		],
		"on_update": "rheinwerk_mes.warehouse.reservations.on_stock_entry_update",
		"on_submit": [
			"rheinwerk_mes.warehouse.reservations.on_stock_entry_submit",
			# W2-1: genealogy links are written from the posting (URS-W2-001).
			"rheinwerk_mes.genealogy.links.on_stock_entry_submit",
		],
		"on_cancel": [
			"rheinwerk_mes.warehouse.reservations.on_stock_entry_cancel",
			"rheinwerk_mes.genealogy.links.on_stock_entry_cancel",
		],
		"on_trash": "rheinwerk_mes.warehouse.reservations.on_stock_entry_trash",
	},
	# W1-1: every `exec_state` change funnels through one validator (URS-W1-001…004).
	"Work Order": {
		"before_insert": "rheinwerk_mes.manufacturing_core.exec_state.set_default_exec_state",
		"validate": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
		"before_update_after_submit": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
		# W1-2: post-transition side effects — reservations released on Declined/Abandoned
		# (URS-W1-009) and the executed transition logged immutably (URS-W1-033).
		"on_update": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
		"on_update_after_submit": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
	},
	# W1-7: the job card's own name is the barcode the terminal scans (URS-W1-028).
	"Job Card": {
		"validate": "rheinwerk_mes.setup.w1_shopfloor.set_job_card_scan_code",
	},
	# W2-2/W2-3: every `qa_state` change funnels through one validator, and the executed
	# transition propagates blocked-ancestor advisories (URS-W2-006, URS-W2-009).
	"Batch": {
		"before_insert": "rheinwerk_mes.genealogy.qa_state.set_default_qa_state",
		"validate": "rheinwerk_mes.genealogy.qa_state.validate_qa_state_change",
		"on_update": "rheinwerk_mes.genealogy.blocking.on_batch_update",
	},
	# W1-4: Accepted recipes are immutable and in-use recipes are locked
	# (URS-W1-016, URS-W1-017); changes need a new BOM version.
	"BOM": {
		"validate": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_update_after_submit": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_cancel": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
	},
}

# W1-1: ordered gate callbacks run by
# `rheinwerk_mes.manufacturing_core.exec_state.transition` before a state change is
# written. Later waves append their gates here — no edit to the state machine needed.
# Each callable takes a `TransitionContext` and either appends German-first messages to
# `context.errors` / returns them, or throws its own modal.
rheinwerk_exec_state_gates = [
	"rheinwerk_mes.manufacturing_core.exec_state.reason_gate",
	"rheinwerk_mes.manufacturing_core.exec_state.anchor_submit_gate",
	"rheinwerk_mes.manufacturing_core.exec_state.shortfall_gate",
	# W1-2: execution gating (URS-W1-005 … URS-W1-008).
	"rheinwerk_mes.execution_gating.gates.acceptance_gate",
	"rheinwerk_mes.execution_gating.gates.recipe_accepted_gate",
	"rheinwerk_mes.execution_gating.gates.completion_gate",
	"rheinwerk_mes.execution_gating.gates.material_availability_gate",
]

# W2-2: ordered gate callbacks run by `rheinwerk_mes.genealogy.qa_state.transition` before
# a batch disposition is written. The W2-4 quality child appends its Quality-Inspection
# gate here — no edit to the state machine needed. Each callable takes a
# `qa_state.TransitionContext` (see `docs/design/W2-genealogy.md`).
rheinwerk_qa_state_gates = [
	"rheinwerk_mes.genealogy.qa_state.reason_gate",
]
